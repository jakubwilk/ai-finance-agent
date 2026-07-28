import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 p-16 text-center">
      <h1 className="text-2xl font-semibold">AI Finance Agent</h1>
      <p className="max-w-md text-muted-foreground">
        Local UI for the LangGraph workflow — graph structure, run history, categorization review.
      </p>
      <Link href="/graph" className="text-primary underline underline-offset-4">
        View master graph
      </Link>
    </main>
  );
}
