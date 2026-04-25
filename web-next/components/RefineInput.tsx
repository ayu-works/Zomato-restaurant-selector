"use client";
import { useState } from "react";

type Props = {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

export function RefineInput({ onSubmit, disabled, placeholder }: Props) {
  const [text, setText] = useState("");
  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSubmit(text.trim());
    setText("");
  };
  return (
    <form
      onSubmit={handle}
      className="rounded-full border border-ink-300/50 bg-white shadow-card pl-5 pr-1.5 py-1.5 flex items-center gap-3"
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder={placeholder ?? "Refine further… e.g. 'Must have outdoor seating'"}
        className="flex-1 bg-transparent text-sm text-ink-900 placeholder:text-ink-500 outline-none py-2 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="h-9 w-9 rounded-full bg-brand-500 text-white flex items-center justify-center hover:bg-brand-600 disabled:opacity-50"
        aria-label="Send"
      >
        <SendIcon />
      </button>
    </form>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}
