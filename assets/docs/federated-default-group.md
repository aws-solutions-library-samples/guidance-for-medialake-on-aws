# Default group for federated (SSO) users

When a user signs in through an external SAML or OIDC identity provider for the first time, Media Lake can add them to a default Cognito group so they get baseline permissions right away.

## How it works

Cognito invokes a different set of Lambda triggers on a federated user's first sign-in than on later ones ([AWS: Lambda triggers for federated users](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-working-with-lambda-triggers.html)):

| Sign-in    | Triggers                                                                                                               |
| ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| First      | Pre sign-up (`PreSignUp_ExternalProvider`), Post confirmation (`PostConfirmation_ConfirmSignUp`), Pre token generation |
| Subsequent | Pre authentication, Post authentication, Pre token generation                                                          |

The assignment lives in the **post confirmation** trigger (`lambdas/auth/post_confirmation`). It runs once per user, right after Cognito creates the profile, and calls `AdminAddUserToGroup` with the `userPoolId` and `userName` from the event. Because Cognito never invokes it again for that user, an administrator who later moves the user to another group, or removes every group to revoke access, is never overridden.

The **pre token generation** trigger (`lambdas/auth/pre_token_generation`) only shapes claims. It turns the user's Cognito groups into the `custom:permissions` claim and never changes membership.

The post confirmation trigger ignores:

- `PostConfirmation_ConfirmForgotPassword`, which fires when a local user resets their password.
- Locally created users (not `EXTERNAL_PROVIDER` and no `identities`). The users API puts them in groups.

## Choosing the group

1. **System Settings → User Provisioning** in the UI. This writes `PK=SYSTEM_SETTINGS, SK=JIT_PROVISIONING` (`enabled`, `defaultGroupId`) to the system-settings table. The trigger reads it on every invocation, so a change applies to the next new federated user without a redeploy.
2. **`authZ.jit_provisioning.default_group`** in `config.json`. This is passed to the trigger as the `JIT_DEFAULT_GROUP` environment variable. It is the fallback when no setting has been saved, or when the settings table cannot be read.

The UI setting is not written back into the environment variable. The environment variable belongs to CloudFormation, so a UI-written value would be silently reverted by the next deploy.

With `allow_idp_group_assertions` and an `idp_group_mapping`, groups asserted by the identity provider (the `custom:groups` attribute) replace the default. Only mapped names are honoured, so an identity provider cannot name a Media Lake group directly. If no asserted group can be assigned, the trigger falls back to the default group.

## Configuration

```json
"authZ": {
  "identity_providers": [ ... ],
  "jit_provisioning": { "enabled": true, "default_group": "read-only" }
}
```

`enabled` is a deploy-time switch. When it is false the post confirmation Lambda is not created and is detached from the pool, so no Lambda can change group membership. Choosing `superAdministrators` as the default requires `allow_privileged_default_group: true`.

## Failures

The trigger never raises, because an exception would fail the user's sign-in. Since it only fires once, a failed assignment is not retried. The failure is logged as an error and counted in the `MediaLake/Auth` CloudWatch metric `DefaultGroupAssignmentFailed`. Assign the group manually in **Users**.

Group membership becomes token claims at sign-in, so a user whose groups change must sign out and back in.
