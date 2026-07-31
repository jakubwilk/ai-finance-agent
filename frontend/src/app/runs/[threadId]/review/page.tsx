import { ReviewQueuePage } from '@/modules/runs/pages/ReviewQueuePage';

export default async function Page({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  return <ReviewQueuePage threadId={threadId} />;
}
