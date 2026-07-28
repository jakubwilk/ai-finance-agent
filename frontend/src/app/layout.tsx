import type { Metadata } from 'next';
import { Geist, Geist_Mono, JetBrains_Mono, Nunito_Sans } from 'next/font/google';

import './globals.css';
import { cn } from '@/lib/utils';
import { AppNav } from '@/modules/common/components/AppNav';

const nunitoSansHeading = Nunito_Sans({ subsets: ['latin'], variable: '--font-heading' });

const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'AI Finance Agent',
  description: 'Local UI for the AI Finance Agent LangGraph workflow',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn(
        'h-full',
        'antialiased',
        geistSans.variable,
        geistMono.variable,
        'font-mono',
        jetbrainsMono.variable,
        nunitoSansHeading.variable,
      )}
    >
      <body className="flex h-full min-h-full flex-col">
        <AppNav />
        <main className="flex min-h-0 flex-1 flex-col">{children}</main>
      </body>
    </html>
  );
}
