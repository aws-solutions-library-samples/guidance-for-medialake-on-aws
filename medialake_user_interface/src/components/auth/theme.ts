import { Theme } from "@aws-amplify/ui-react";
import { amplifyTheme } from "../../theme/theme";

export const theme: Theme = amplifyTheme;

export const components = {
  Header() {
    return null;
  },
  Footer() {
    return null;
  },
  SignIn: {
    Header() {
      return null;
    },
    Footer() {
      return null;
    },
  },
};
