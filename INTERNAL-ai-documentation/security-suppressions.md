# Security Scanner Suppressions Documentation

## Overview

This document describes the security scanner suppressions added to address false positive findings from bandit security scanning.

## Suppressions Applied

### B102 - Use of exec() detected

**Files affected:**

- `lambdas/nodes/audio_proxy/index.py` (line 81)
- `lambdas/nodes/video_proxy_and_thumbnail/index.py` (line 99)
- `lambdas/nodes/audio_transcription_transcribe/index.py` (line 43)
- `lambdas/nodes/api_handler/index.py` (lines 163, 332)
- `lambdas/nodes/bedrock_content_processor/index.py` (line 330)
- `lambdas/nodes/audio_transcription_transcribe_status/index.py` (line 65)
- `lambdas/nodes/check_media_convert_status/index.py` (line 75)

**Justification:**
These `exec()` calls are used for controlled execution of trusted S3 template files. The code being executed comes from S3 objects that are part of the application's template system, not from user input. This is a legitimate architectural pattern for dynamic template processing.

**Suppression comment:** `# nosec B102 - Controlled execution of trusted S3 templates`

### B701 - jinja2 autoescape disabled

**Files affected:**

- `lambdas/nodes/audio_proxy/index.py` (lines 100, 120)
- `lambdas/nodes/video_proxy_and_thumbnail/index.py` (lines 122, 140)
- `lambdas/nodes/audio_transcription_transcribe/index.py` (lines 77, 102)
- `lambdas/nodes/api_handler/index.py` (lines 279, 296, 314)
- `lambdas/nodes/audio_transcription_transcribe_status/index.py` (lines 97, 119)
- `lambdas/nodes/check_media_convert_status/index.py` (lines 96, 109)

**Justification:**
These Jinja2 Environment instances are used for template rendering with controlled, trusted input from S3 template files. The templates are part of the application architecture and not user-provided content, making autoescape unnecessary in this context.

**Suppression comment:** `# nosec B701 - Controlled template rendering with trusted input`

## Total Suppressions

- **B102 (exec usage):** 8 suppressions
- **B701 (jinja2 autoescape):** 13 suppressions
- **Total:** 21 suppressions

## Review Process

These suppressions were added after careful review of each finding to confirm they are legitimate false positives. All suppressed code involves controlled execution or rendering of trusted template content from S3, not user-provided input.

## Future Maintenance

When modifying the affected files, ensure that:

1. The suppression comments remain accurate
2. Any new similar patterns follow the same suppression approach
3. The security context (trusted S3 templates) remains unchanged
