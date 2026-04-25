export function Header() {
  return (
    <header className="border-b border-ink-300/40 bg-white/80 backdrop-blur sticky top-0 z-20">
      <div className="mx-auto max-w-6xl px-6 py-3 flex items-center gap-8">
        <div className="text-brand-500 font-bold text-lg tracking-tight">Zomato AI</div>
        <nav className="hidden sm:flex items-center gap-6 text-sm text-ink-700">
          <a className="hover:text-brand-600" href="#">Delivery</a>
          <a className="hover:text-brand-600" href="#">History</a>
          <a className="text-brand-500 font-semibold border-b-2 border-brand-500 pb-1" href="#">
            AI Concierge
          </a>
          <a className="hover:text-brand-600" href="#">Profile</a>
        </nav>
        <div className="flex-1" />
        <div className="flex items-center gap-4 text-ink-500">
          <BellIcon />
          <CartIcon />
        </div>
      </div>
    </header>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 003.4 0" />
    </svg>
  );
}

function CartIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.7 13.4a2 2 0 002 1.6h9.7a2 2 0 002-1.6L23 6H6" />
    </svg>
  );
}
