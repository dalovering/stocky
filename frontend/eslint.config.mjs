// Next.js 16 ships a native ESLint flat config — use it directly.
import next from "eslint-config-next";

const eslintConfig = [
  ...next,
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    rules: {
      // This React-Compiler-era rule flags our async fetch-on-mount effects (load() then
      // setState). The setState runs after an `await`, not synchronously, so it does not
      // cause the cascading re-renders the rule guards against — it's a false positive for
      // data loading. All other react-hooks rules stay enabled.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default eslintConfig;
