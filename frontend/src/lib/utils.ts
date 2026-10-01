import { createCn } from "cn/config";

/** Textstile aus globals.css (Figma "iOS/…" und "Tag/…"): Schriftgroessen, keine Textfarben. */
export const TEXT_STYLES = ["large-title", "title-1", "title-2", "title-3", "headline", "body", "callout", "subhead", "footnote", "caption-1", "caption-2", "tag", "tag-sm"];

/**
 * clsx + Konfliktaufloesung wie tailwind-merge, ergaenzt um die eigenen Theme-Namen: sonst hielte cn "text-footnote"
 * fuer eine Textfarbe und striche es neben "text-muted-foreground".
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "font-size": [{ text: TEXT_STYLES }],
      shadow: [{ shadow: ["card", "floating"] }],
      "backdrop-blur": [{ "backdrop-blur": ["bar"] }],
    },
  },
});
