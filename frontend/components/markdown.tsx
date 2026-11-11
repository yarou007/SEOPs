import ReactMarkdown from "react-markdown";

/** Renders model-written Markdown; raw HTML in the text is dropped, never rendered. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown skipHtml>{children}</ReactMarkdown>
    </div>
  );
}
