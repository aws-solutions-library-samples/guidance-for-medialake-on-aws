import { useContext, useEffect, useState, useCallback } from "react";
import { CognitoUserPool } from "amazon-cognito-identity-js";
import { AwsConfigContext } from "./aws-config-context";
import { StorageHelper } from "../helpers/storage-helper";

export const useUserPool = () => {
  const awsConfig = useContext(AwsConfigContext);
  const [userPool, setUserPool] = useState<CognitoUserPool | null>(null);

  const initializeUserPool = useCallback(() => {
    const config = awsConfig || StorageHelper.getAwsConfig();
    if (
      config &&
      config.Auth?.Cognito?.userPoolId &&
      config.Auth?.Cognito?.userPoolClientId
    ) {
      const pool = new CognitoUserPool({
        UserPoolId: config.Auth.Cognito.userPoolId,
        ClientId: config.Auth.Cognito.userPoolClientId,
      });
      setUserPool(pool);
      console.log("User Pool created successfully");
    } else {
      console.error("AWS Config is missing required User Pool information");
    }
  }, [awsConfig]);

  useEffect(() => {
    initializeUserPool();
  }, [initializeUserPool]);

  return { userPool, reinitializeUserPool: initializeUserPool };
};
