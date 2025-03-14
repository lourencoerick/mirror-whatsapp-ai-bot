import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      "@typescript-eslint/no-unused-vars": "error", // Erro para variáveis não usadas
      "@typescript-eslint/no-explicit-any": "error", // ❌ Proíbe `any` implícito
      "react-hooks/rules-of-hooks": "error", // Garante boas práticas de hooks
      "react-hooks/exhaustive-deps": "warn", // Verifica dependências de hooks
      // "no-console": "warn", // Evita consoles no código
      "no-debugger": "error", // Impede `debugger` no código
      "no-unused-vars": "off", // Para evitar conflitos com @typescript-eslint/no-unused-vars
    },
  },
];

export default eslintConfig;
