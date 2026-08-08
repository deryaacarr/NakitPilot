"use client";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/ui/theme-provider";

export function ThemeToggle() {
  const { resolved, toggle } = useTheme();
  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      onClick={toggle}
      aria-label={resolved === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
      title={resolved === "dark" ? "Açık tema" : "Koyu tema"}
    >
      {resolved === "dark" ? "Açık" : "Koyu"}
    </Button>
  );
}
