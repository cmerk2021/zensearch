"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * Renders Markdown (the format emitted by the AI models and stored in notes) as
 * styled React elements. Raw HTML is intentionally not enabled, so this is safe
 * against injection — react-markdown escapes content and strips dangerous URL
 * schemes by default.
 */
export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn("text-sm leading-relaxed text-foreground", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node, ...props }) => (
            <h1 className="mb-2 mt-4 text-lg font-semibold first:mt-0" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="mb-2 mt-4 text-base font-semibold first:mt-0" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="mb-1.5 mt-3 text-sm font-semibold first:mt-0" {...props} />
          ),
          h4: ({ node, ...props }) => (
            <h4 className="mb-1.5 mt-3 text-sm font-semibold first:mt-0" {...props} />
          ),
          p: ({ node, ...props }) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
          a: ({ node, ...props }) => (
            <a
              className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          ul: ({ node, ...props }) => (
            <ul className="my-2 list-disc space-y-1 pl-5 marker:text-muted" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted" {...props} />
          ),
          li: ({ node, ...props }) => <li className="pl-0.5" {...props} />,
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="my-2 border-l-2 border-accent/40 pl-3 italic text-muted"
              {...props}
            />
          ),
          code: ({ node, className: codeClass, children, ...props }) => {
            const isBlock = /language-/.test(codeClass ?? "");
            if (isBlock) {
              return (
                <code
                  className={cn(
                    "block overflow-x-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-xs leading-relaxed",
                    codeClass,
                  )}
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.85em]"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ node, ...props }) => <pre className="my-2" {...props} />,
          hr: ({ node, ...props }) => <hr className="my-4 border-border" {...props} />,
          table: ({ node, ...props }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs" {...props} />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th
              className="border border-border bg-surface-2 px-2 py-1 text-left font-medium"
              {...props}
            />
          ),
          td: ({ node, ...props }) => (
            <td className="border border-border px-2 py-1" {...props} />
          ),
          strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
