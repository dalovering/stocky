"use client";

import { Box, Button, Flex, Text } from "@radix-ui/themes";
import { ResetIcon } from "@radix-ui/react-icons";

// Normalize "empty" values so an optional field left blank doesn't read as changed: "", null and
// undefined are all treated as the same empty value.
function normalize(value: unknown): unknown {
  return value === "" || value === undefined ? null : value;
}

/** True when `value` differs from its default (with empty-string/null/undefined treated alike). */
export function isModified(value: unknown, fallback: unknown): boolean {
  return normalize(value) !== normalize(fallback);
}

/**
 * A labelled form field that signals when its value has been changed away from the default.
 *
 * When `modified` is true the field is shaded (amber accent bar + tint), the label is highlighted,
 * and a Reset control appears that restores the default via `onReset`. Used across the admin edit
 * modals so "this isn't the default" is visible at a glance and one click reverts it.
 */
export function Field({
  label,
  hint,
  children,
  modified = false,
  onReset,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  modified?: boolean;
  onReset?: () => void;
}) {
  return (
    <Box asChild>
      <label>
        <Flex justify="between" align="center" gap="2" mb="1">
          <Text size="2" as="div" color={modified ? "amber" : undefined}>
            {label}
            {hint && (
              <Text size="1" color="gray" ml="1">
                {hint}
              </Text>
            )}
            {modified && (
              <Text size="1" weight="medium" color="amber" ml="2">
                changed
              </Text>
            )}
          </Text>
          {modified && onReset && (
            <Button
              type="button"
              size="1"
              variant="ghost"
              color="gray"
              // Inside a <label>, clicks bubble to the control — stop the default so Reset doesn't
              // also focus/toggle the field it's resetting.
              onClick={(e) => {
                e.preventDefault();
                onReset();
              }}
            >
              <ResetIcon /> Reset
            </Button>
          )}
        </Flex>
        <Box
          style={{
            // Reserve the accent-bar width on every field so toggling it doesn't shift the layout.
            borderLeft: `3px solid ${modified ? "var(--amber-8)" : "transparent"}`,
            background: modified ? "var(--amber-2)" : undefined,
            paddingLeft: 8,
            borderRadius: "0 4px 4px 0",
          }}
        >
          {children}
        </Box>
      </label>
    </Box>
  );
}
