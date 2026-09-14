/// <reference types="vite/client" />

declare const process: {
  env: {
    REACT_APP_API_BASE_URL?: string;
    REACT_APP_API_KEY?: string;
    REACT_APP_TENANT_ID?: string;
    REACT_APP_USER_ID?: string;
    REACT_APP_AUTH_TOKEN?: string;
    REACT_APP_SKIP_AUTH?: string;
    REACT_APP_HR_CURRENCY?: string;
    REACT_APP_DATAMART_GROUNDING_CONFIRM?: string;
    NODE_ENV?: string;
  };
};
