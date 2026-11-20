/** The Atlas logo: a shield around a globe with connected nodes. */
export function AtlasMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" fill="none" className={className} role="img" aria-label="Atlas">
      <path
        d="M24 4.5c-6.2 3.6-12 5.6-17.5 6.6v12.4c0 10.6 7.3 16.9 17.5 20.5 10.2-3.6 17.5-9.9 17.5-20.5V11.1C36 10.1 30.2 8.1 24 4.5Z"
        className="fill-white stroke-[#0b1f44] dark:fill-[#0f182b] dark:stroke-[#c7d0ea]"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <g className="stroke-[#4f46e5] dark:stroke-[#818cf8]" strokeWidth="2">
        <ellipse cx="24" cy="24.5" rx="9.5" ry="14" />
        <path d="M24 10.5v28M9.5 23.5c9.5 1.8 19.5 1.8 29 0" />
      </g>
      <g className="stroke-[#14b8a6]" strokeWidth="2" strokeLinecap="round">
        <path d="M26.5 26 18 18.5M26.5 26l9-8M26.5 26l-9 6" />
      </g>
      <g className="fill-[#14b8a6]">
        <circle cx="26.5" cy="26" r="3.2" />
        <circle cx="18" cy="18.5" r="2" />
        <circle cx="35.5" cy="18" r="2" />
        <circle cx="17.5" cy="32" r="2" />
      </g>
    </svg>
  );
}
