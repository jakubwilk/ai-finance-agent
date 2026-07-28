import { client } from '@/modules/common/api/client';
import { mockClient } from '@/modules/common/api/mockClient';
import type { ApiClient } from '@/modules/common/models/api';

// Mock by default until the FastAPI backend (Plan A step 13) exists.
// Set NEXT_PUBLIC_USE_MOCK_API=false to point the UI at a real backend.
const useMock = process.env.NEXT_PUBLIC_USE_MOCK_API !== 'false';

export const apiClient: ApiClient = useMock ? mockClient : client;

export * from '@/modules/common/models/api';
