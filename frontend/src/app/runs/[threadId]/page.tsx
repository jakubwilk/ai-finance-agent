import { RunDetailPage } from '@/modules/runs/pages/RunDetailPage';

export default async function Page({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  return <RunDetailPage threadId={threadId} />;
}
