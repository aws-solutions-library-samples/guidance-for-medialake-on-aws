#!/usr/bin/env bash
set -euo pipefail

# Script: trigger_embedding_pipeline.sh
# Description: Backfill a TwelveLabs embedding pipeline over already-ingested
#              MediaLake assets by starting one Step Functions execution per
#              asset (keyed by InventoryID). Event-triggered embedding pipelines
#              have no manual "run" button, so we start their state machine
#              directly with the input shape the lambda_middleware expects:
#              {"item":{"inventory_id":"...","params":{}}}.
#
#              Two modes:
#                - Discovery: scan the asset table by media type (--table).
#                - Explicit:  target specific assets by ID (--inventory-ids),
#                             ideal for testing one or a few before a full run.

DEPENDENCIES=(aws jq)
SCRIPT_NAME=$(basename "$0")

log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO  $*"; }
log_warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN  $*"; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR $*" >&2; }

function usage() {
    cat <<EOF

Backfill an embedding pipeline over existing MediaLake assets.

Starts one Step Functions execution per asset, keyed by InventoryID. Either
discover assets by scanning the asset table (--table) or target specific assets
by ID (--inventory-ids). Defaults to a dry run that only lists matches; pass
--execute to actually start executions.

Usage: ${SCRIPT_NAME} --state-machine-arn <arn> (--table <name> | --inventory-ids <ids>) [OPTIONS]

Required:
    -s, --state-machine-arn  <arn>    State machine ARN of the embedding pipeline

    and one of:
    -t, --table              <name>   Asset DynamoDB table (discovery mode)
    -i, --inventory-ids      <ids>    Comma-separated InventoryID(s) to target directly

Options:
    -m, --media-type   <type>   Video | Audio | Image   (default: Video; discovery mode only)
    -p, --prefix       <str>    Only assets whose S3 object key (bucket stripped) starts with this prefix (discovery mode only)
    --execute                   Actually start executions (default is dry run)
    --region           <name>   AWS region (else uses your configured default)
    --profile          <name>   AWS CLI profile
    -h, --help                  Show this help

Dependencies: ${DEPENDENCIES[*]}

Examples:
    # Test a single asset (dry run, then add --execute)
    ${SCRIPT_NAME} -s arn:...:stateMachine:... -i asset:uuid:abc123-def456

    # Test a few specific assets
    ${SCRIPT_NAME} -s arn:...:stateMachine:... \\
        -i asset:uuid:abc123,asset:uuid:def456 --execute

    # Discovery dry run: list ingested videos and what would be triggered
    ${SCRIPT_NAME} -t medialake-asset-table-prod -s arn:aws:states:us-east-1:111122223333:stateMachine:medialake_Marengo30VideoS3Vectors

    # Backfill all videos under a prefix
    ${SCRIPT_NAME} -t medialake-asset-table-prod -s arn:...:stateMachine:... \\
        --prefix uploads/2024 --execute

EOF
    exit "${1:-0}"
}

function exit_on_missing_tools() {
    for cmd in "$@"; do
        command -v "$cmd" &>/dev/null || { log_error "'$cmd' not found in PATH"; exit 1; }
    done
}

# Scan the asset table for the requested media type and print TSV rows:
#   <inventory_id>\t<object_key>
function discover_assets() {
    # Type is a reserved word in DynamoDB, hence the #t alias.
    # StoragePath is a top-level "{bucket}:{key}" string; strip the bucket prefix
    # (everything up to and including the first colon) to recover the object key.
    aws dynamodb scan ${AWS_ARGS[@]+"${AWS_ARGS[@]}"} \
        --table-name "$TABLE" \
        --filter-expression "DigitalSourceAsset.#t = :mt" \
        --expression-attribute-names '{"#t":"Type"}' \
        --expression-attribute-values "{\":mt\":{\"S\":\"${MEDIA_TYPE}\"}}" \
        --projection-expression "InventoryID, StoragePath" \
        --output json 2>/dev/null \
    | jq -r '
        .Items[]
        | [ .InventoryID.S,
            ((.StoragePath.S // "") | sub("^[^:]*:"; "") | if . == "" then "(no-key)" else . end)
          ] | @tsv
    '
}

function start_execution() {
    local inventory_id="$1"
    local input
    input=$(jq -nc --arg id "$inventory_id" '{item:{inventory_id:$id,params:{}}}')

    aws stepfunctions start-execution ${AWS_ARGS[@]+"${AWS_ARGS[@]}"} \
        --state-machine-arn "$STATE_MACHINE_ARN" \
        --input "$input" \
        --query 'executionArn' --output text
}

# Populate the global `to_run` array from explicit --inventory-ids.
function select_explicit() {
    local inv
    log_info "Targeting ${#INVENTORY_IDS[@]} explicitly provided InventoryID(s)."
    for inv in "${INVENTORY_IDS[@]}"; do
        to_run+=("$inv")
        printf '  %s\n' "$inv"
    done
}

# Populate the global `to_run` array by scanning the asset table.
function select_from_table() {
    local temp_file
    temp_file=$(mktemp)
    trap "rm -f '$temp_file'" RETURN

    log_info "Scanning table '$TABLE' for media type '$MEDIA_TYPE'..."
    discover_assets >"$temp_file"
    [[ "${PIPESTATUS[0]}" -ne 0 ]] && { log_error "DynamoDB scan failed"; return 1; }

    local total skipped_prefix=0
    total=$(wc -l <"$temp_file" | tr -d ' ')
    log_info "Found $total '$MEDIA_TYPE' asset(s) in table."

    local inv key
    while IFS=$'\t' read -r inv key; do
        if [[ -n "$PREFIX" && "$key" != "$PREFIX"* ]]; then
            skipped_prefix=$((skipped_prefix + 1)); continue
        fi
        to_run+=("$inv")
        printf '  %s\t%s\n' "$inv" "$key"
    done <"$temp_file"

    log_info "Skipped (prefix): $skipped_prefix"
}

function run_backfill() {
    local -a to_run=()

    if [[ ${#INVENTORY_IDS[@]} -gt 0 ]]; then
        select_explicit
    else
        select_from_table
    fi

    local selected=${#to_run[@]}
    log_info "Selected: $selected"

    if [[ "$EXECUTE" != true ]]; then
        log_info "Dry run — no executions started. Re-run with --execute to trigger."
        return 0
    fi
    if [[ "$selected" -eq 0 ]]; then
        log_warn "Nothing to trigger."; return 0
    fi

    read -rp "Start $selected Step Functions execution(s)? (y/n): " -n 1 reply
    echo
    [[ ! "$reply" =~ ^[Yy]$ ]] && { log_info "Aborted."; return 0; }

    local started=0 failed=0 arn
    for inv in "${to_run[@]}"; do
        if arn=$(start_execution "$inv"); then
            log_info "Started $inv -> $arn"
            started=$((started + 1))
        else
            log_error "Failed to start execution for $inv"
            failed=$((failed + 1))
        fi
    done
    log_info "Done. Started: $started | Failed: $failed"
}

function main() {
    TABLE=""
    STATE_MACHINE_ARN=""
    MEDIA_TYPE="Video"
    PREFIX=""
    EXECUTE=false
    AWS_ARGS=()
    INVENTORY_IDS=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
        -t | --table)             TABLE="$2";             shift 2 ;;
        -s | --state-machine-arn) STATE_MACHINE_ARN="$2"; shift 2 ;;
        -m | --media-type)        MEDIA_TYPE="$2";        shift 2 ;;
        -p | --prefix)            PREFIX="$2";            shift 2 ;;
        -i | --inventory-ids)
            # Split a comma-separated list into the INVENTORY_IDS array.
            IFS=',' read -ra INVENTORY_IDS <<<"$2"
            shift 2
            ;;
        --execute)                EXECUTE=true;           shift   ;;
        --region)                 AWS_ARGS+=(--region "$2");  shift 2 ;;
        --profile)                AWS_ARGS+=(--profile "$2"); shift 2 ;;
        -h | --help)              usage ;;
        *) log_error "Unknown option: $1"; usage 1 ;;
        esac
    done

    [[ -z "$STATE_MACHINE_ARN" ]] && { log_error "--state-machine-arn is required"; usage 1; }

    # Exactly one source of assets: explicit IDs or a table scan.
    if [[ ${#INVENTORY_IDS[@]} -gt 0 && -n "$TABLE" ]]; then
        log_error "Use either --inventory-ids or --table, not both"; usage 1
    fi
    if [[ ${#INVENTORY_IDS[@]} -eq 0 && -z "$TABLE" ]]; then
        log_error "One of --inventory-ids or --table is required"; usage 1
    fi

    # --media-type / --prefix only apply to table-discovery mode.
    case "$MEDIA_TYPE" in
        Video | Audio | Image) ;;
        *) log_error "--media-type must be Video, Audio, or Image"; exit 1 ;;
    esac

    exit_on_missing_tools "${DEPENDENCIES[@]}"
    run_backfill
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
    exit 0
fi
