import js from "@eslint/js";
import a11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

// ESLint flat config replaces a rule entirely for the last matching block, it
// does not merge pattern arrays across blocks — so every block below that
// touches "no-restricted-imports" lists every pattern that must apply to its
// file set, even patterns already declared elsewhere.
const noInfrastructureFromUi = {
  group: ["**/infrastructure/**"],
  message: "ui/ must not import infrastructure/. Consume a hook.",
};
const noReactQueryFromUi = {
  group: ["@tanstack/react-query"],
  message: "ui/ must not import react-query. Consume a hook.",
};
const noFeaturesFromShared = {
  group: ["**/features/**"],
  message: "shared/ must not import from features/.",
};
const noFeatureInternals = {
  group: ["**/features/*/*/**"],
  message: "Import a feature through its index.ts, not its internals.",
};

// Error subclasses are exempt: instanceof and stack capture need a real class.
const noClasses = {
  selector: "ClassDeclaration[superClass.name!='Error']",
  message:
    "No classes. Use arrow functions and factories returning object literals. ErrorBoundary is the only exception, because React offers no hook for componentDidCatch.",
};
const noInlineTypes = [
  {
    selector: "TSInterfaceDeclaration",
    message: "Declare types in a sibling *.types.ts file and import them.",
  },
  {
    selector: "TSTypeAliasDeclaration",
    message: "Declare types in a sibling *.types.ts file and import them.",
  },
];

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        project: "./tsconfig.json",
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      "jsx-a11y": a11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...a11y.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "error",
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      // TypeScript already checks undefined references; ESLint's version does not see ambient/global types (vitest globals) and would false-positive.
      "no-undef": "off",
      "func-style": ["error", "expression", { allowArrowFunctions: true }],
      "prefer-arrow-callback": "error",
    },
  },
  {
    // Modern React only, and types live beside the module rather than inside it.
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.types.ts", "src/**/*.d.ts"],
    rules: {
      "no-restricted-syntax": ["error", noClasses, ...noInlineTypes],
    },
  },
  {
    // A types file is the declared home for types; it still may not hold a class.
    files: ["src/**/*.types.ts"],
    rules: { "no-restricted-syntax": ["error", noClasses] },
  },
  {
    // React provides no hook equivalent for componentDidCatch.
    files: ["src/app/ErrorBoundary.tsx"],
    rules: { "no-restricted-syntax": ["error", ...noInlineTypes] },
  },
  {
    // Cross-feature access goes through the public index only — applies everywhere.
    files: ["src/**"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [noFeatureInternals] }],
    },
  },
  {
    // shared/ is transversal: the arrow points one way only. Ban goes further
    // than noFeatureInternals (it also blocks importing a feature's own index).
    files: ["src/shared/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        { patterns: [noFeaturesFromShared, noFeatureInternals] },
      ],
    },
  },
  {
    // UI may not reach adapters or the query library directly.
    files: ["src/features/*/ui/**"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            noInfrastructureFromUi,
            noReactQueryFromUi,
            noFeatureInternals,
          ],
        },
      ],
    },
  },
);
