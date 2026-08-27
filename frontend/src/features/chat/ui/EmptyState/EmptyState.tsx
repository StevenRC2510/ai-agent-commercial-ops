import {
  EXAMPLE,
  EXAMPLES,
  EXAMPLE_ARROW,
  EXAMPLE_PROMPTS,
  LEAD,
  LEAD_TEXT,
  TITLE,
  TITLE_TEXT,
  WRAPPER,
} from "./EmptyState.constants";
import type { EmptyStateProps } from "./EmptyState.types";

export const EmptyState = ({ onPick }: EmptyStateProps) => (
  <div className={WRAPPER}>
    <div>
      <h2 className={TITLE}>{TITLE_TEXT}</h2>
      <p className={LEAD}>{LEAD_TEXT}</p>
    </div>
    <ul className={EXAMPLES}>
      {EXAMPLE_PROMPTS.map((prompt) => (
        <li key={prompt}>
          <button type="button" onClick={() => onPick(prompt)} className={EXAMPLE}>
            {prompt}
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true" className={EXAMPLE_ARROW}>
              <path
                d="M6 3.5 10.5 8 6 12.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </li>
      ))}
    </ul>
  </div>
);
