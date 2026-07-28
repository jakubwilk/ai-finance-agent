import Link from 'next/link';

const LINKS = [
  { href: '/graph', label: 'Graph' },
  { href: '/runs', label: 'Runs' },
];

export function AppNav() {
  return (
    <nav className="flex gap-4 border-b border-border px-4 py-3 text-sm">
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
