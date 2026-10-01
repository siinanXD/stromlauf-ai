"use client";

import { memo, useMemo } from "react";
import ReactMarkdown, { type Components, type Options, type UrlTransform } from "react-markdown";

import { splitBlocks } from "./markdownText";

export interface MarkdownRender {
  components: Components;
  remarkPlugins: NonNullable<Options["remarkPlugins"]>;
  urlTransform: UrlTransform;
}

/**
 * Ein Absatz; zwischengespeichert ueber seinen Text (und die Version der Umgebung: Belege, Kennzeichen, aktiver
 * Beleg). Beim Streamen aendert sich nur der letzte Absatz, die anderen werden nicht neu geparst.
 */
const MarkdownBlock = memo(
  function MarkdownBlock({ text, render }: { text: string; version: string; render: MarkdownRender }) {
    return (
      <ReactMarkdown remarkPlugins={render.remarkPlugins} components={render.components} urlTransform={render.urlTransform}>
        {text}
      </ReactMarkdown>
    );
  },
  (prev, next) => prev.text === next.text && prev.version === next.version,
);

export function Markdown({ text, render, version }: { text: string; render: MarkdownRender; version: string }) {
  const blocks = useMemo(() => splitBlocks(text), [text]);
  return (
    <>
      {blocks.map((block, index) => (
        // Schluessel ist die Position: der letzte Absatz waechst beim Streamen und wird aktualisiert, nicht neu aufgebaut.
        <MarkdownBlock key={index} text={block} version={version} render={render} />
      ))}
    </>
  );
}
