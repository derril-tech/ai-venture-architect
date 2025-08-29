/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverActions: {
            allowedOrigins: ['localhost:3000', 'localhost:3001']
        }
    },
    env: {
        CUSTOM_KEY: process.env.CUSTOM_KEY,
    },
    async rewrites() {
        return [
            {
                source: '/api/v1/:path*',
                destination: `${process.env.API_URL || 'http://localhost:8000'}/v1/:path*`
            }
        ]
    }
}

module.exports = nextConfig
