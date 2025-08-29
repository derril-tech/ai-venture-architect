import { Container, Title, Text, Button, Group } from '@mantine/core'
import { TrendingUp, Users, Target } from 'lucide-react'

export default function HomePage() {
    return (
        <Container size="lg" className="py-16">
            <div className="text-center mb-16">
                <Title order={1} className="text-5xl font-bold mb-6 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    AI Venture Architect
                </Title>
                <Text size="xl" className="text-gray-600 max-w-2xl mx-auto mb-8">
                    Multi-agent market research & AI product ideation platform that continuously ingests market signals
                    and generates validated product briefs with investor-ready artifacts.
                </Text>
                <Group justify="center" gap="md">
                    <Button size="lg" variant="filled">
                        Get Started
                    </Button>
                    <Button size="lg" variant="outline">
                        Learn More
                    </Button>
                </Group>
            </div>

            <div className="grid md:grid-cols-3 gap-8 mt-16">
                <div className="text-center p-6">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 text-blue-600" />
                    <Title order={3} className="mb-3">Market Intelligence</Title>
                    <Text className="text-gray-600">
                        Trend scans, growth signals, whitespace analysis, and competitor matrices with real-time updates.
                    </Text>
                </div>

                <div className="text-center p-6">
                    <Target className="w-12 h-12 mx-auto mb-4 text-purple-600" />
                    <Title order={3} className="mb-3">Product Validation</Title>
                    <Text className="text-gray-600">
                        UVP development, ICP analysis, problem hypotheses, and MVP feature prioritization.
                    </Text>
                </div>

                <div className="text-center p-6">
                    <Users className="w-12 h-12 mx-auto mb-4 text-green-600" />
                    <Title order={3} className="mb-3">Business Modeling</Title>
                    <Text className="text-gray-600">
                        TAM/SAM/SOM analysis, pricing strategies, CAC/LTV modeling, and GTM planning.
                    </Text>
                </div>
            </div>
        </Container>
    )
}
