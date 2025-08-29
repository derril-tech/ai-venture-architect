import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
    title: 'AI Venture Architect',
    description: 'Multi-agent market research & AI product ideation platform',
}

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 5 * 60 * 1000, // 5 minutes
            retry: 1,
        },
    },
})

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className={inter.className}>
                <QueryClientProvider client={queryClient}>
                    <MantineProvider>
                        <Notifications />
                        {children}
                        <ReactQueryDevtools initialIsOpen={false} />
                    </MantineProvider>
                </QueryClientProvider>
            </body>
        </html>
    )
}
