// index.js
import React from "react";
import ReactDOM from "react-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import App from "./App";

ReactDOM.render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
  document.getElementById("root") as HTMLElement,
);
