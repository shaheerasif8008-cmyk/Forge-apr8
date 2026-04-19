const { execSync } = require("node:child_process");

const env = {
  ...process.env,
  FORGE_EMPLOYEE_NAME: process.env.FORGE_EMPLOYEE_NAME || "Forge Employee",
  FORGE_EMPLOYEE_ID: process.env.FORGE_EMPLOYEE_ID || "forge-employee",
};

execSync("next build && electron-builder", {
  stdio: "inherit",
  env,
});
