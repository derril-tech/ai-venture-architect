'use client'

import { useState } from 'react'
import {
    Container,
    Grid,
    Card,
    Text,
    Title,
    Badge,
    Button,
    Group,
    Stack,
    Textarea,
    TextInput,
    NumberInput,
    Progress,
    Tabs,
    ActionIcon,
    Tooltip,
    Modal,
    ScrollArea,
    Divider,
    Alert,
    Anchor
} from '@mantine/core'
import {
    IconBulb,
    IconUsers,
    IconTarget,
    IconRocket,
    IconChartLine,
    IconCode,
    IconShield,
    IconEdit,
    IconSave,
    IconExternalLink,
    IconInfoCircle,
    IconStar,
    IconTrendingUp
} from '@tabler/icons-react'

interface IdeaCanvasProps {
    idea: {
        id: string
        title: string
        description: string
        uvp?: string
        problem_statement?: string
        solution_approach?: string
        icps?: Record<string, any>
        target_segments?: string[]
        mvp_features?: string[]
        roadmap?: Record<string, any>
        positioning?: string
        tam_sam_som?: Record<string, any>
        unit_economics?: Record<string, any>
        pricing_model?: string
        tech_stack?: Record<string, any>
        build_vs_buy?: Record<string, any>
        technical_risks?: string[]
        gtm_strategy?: Record<string, any>
        channels?: string[]
        risks?: Record<string, any>
        compliance_notes?: string[]
        attractiveness_score?: number
        confidence_score?: number
        score_breakdown?: Record<string, number>
        sources?: string[]
        citations?: Record<string, string>
        status: string
        created_at: string
    }
    onUpdate?: (updates: Partial<typeof idea>) => void
    readonly?: boolean
}

export function IdeaCanvas({ idea, onUpdate, readonly = false }: IdeaCanvasProps) {
    const [activeTab, setActiveTab] = useState<string>('overview')
    const [editMode, setEditMode] = useState(false)
    const [showCitations, setShowCitations] = useState(false)
    const [localIdea, setLocalIdea] = useState(idea)

    const handleSave = () => {
        onUpdate?.(localIdea)
        setEditMode(false)
    }

    const handleFieldUpdate = (field: string, value: any) => {
        setLocalIdea(prev => ({ ...prev, [field]: value }))
    }

    const getScoreColor = (score?: number) => {
        if (!score) return 'gray'
        if (score >= 8) return 'green'
        if (score >= 6) return 'yellow'
        return 'red'
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'green'
            case 'generating': return 'blue'
            case 'validating': return 'yellow'
            case 'failed': return 'red'
            default: return 'gray'
        }
    }

    return (
        <Container size="xl" py="md">
            {/* Header */}
            <Group justify="space-between" mb="lg">
                <div>
                    <Group gap="sm" mb="xs">
                        <Title order={1}>{localIdea.title}</Title>
                        <Badge color={getStatusColor(localIdea.status)} variant="light">
                            {localIdea.status}
                        </Badge>
                    </Group>
                    <Text c="dimmed" size="sm">
                        Created {new Date(localIdea.created_at).toLocaleDateString()}
                    </Text>
                </div>

                <Group>
                    {!readonly && (
                        <>
                            {editMode ? (
                                <Group gap="xs">
                                    <Button variant="outline" onClick={() => setEditMode(false)}>
                                        Cancel
                                    </Button>
                                    <Button onClick={handleSave} leftSection={<IconSave size={16} />}>
                                        Save Changes
                                    </Button>
                                </Group>
                            ) : (
                                <Button
                                    variant="light"
                                    onClick={() => setEditMode(true)}
                                    leftSection={<IconEdit size={16} />}
                                >
                                    Edit
                                </Button>
                            )}
                        </>
                    )}

                    <Button
                        variant="outline"
                        onClick={() => setShowCitations(true)}
                        leftSection={<IconInfoCircle size={16} />}
                    >
                        Sources
                    </Button>
                </Group>
            </Group>

            {/* Score Cards */}
            <Grid mb="lg">
                <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                    <Card withBorder>
                        <Group justify="space-between">
                            <div>
                                <Text size="sm" c="dimmed">Attractiveness</Text>
                                <Text size="xl" fw={700} c={getScoreColor(localIdea.attractiveness_score)}>
                                    {localIdea.attractiveness_score?.toFixed(1) || 'N/A'}
                                </Text>
                            </div>
                            <IconStar size={24} color="var(--mantine-color-yellow-6)" />
                        </Group>
                        {localIdea.attractiveness_score && (
                            <Progress
                                value={localIdea.attractiveness_score * 10}
                                color={getScoreColor(localIdea.attractiveness_score)}
                                size="sm"
                                mt="xs"
                            />
                        )}
                    </Card>
                </Grid.Col>

                <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                    <Card withBorder>
                        <Group justify="space-between">
                            <div>
                                <Text size="sm" c="dimmed">Confidence</Text>
                                <Text size="xl" fw={700} c={getScoreColor(localIdea.confidence_score)}>
                                    {localIdea.confidence_score?.toFixed(1) || 'N/A'}
                                </Text>
                            </div>
                            <IconShield size={24} color="var(--mantine-color-blue-6)" />
                        </Group>
                        {localIdea.confidence_score && (
                            <Progress
                                value={localIdea.confidence_score * 10}
                                color={getScoreColor(localIdea.confidence_score)}
                                size="sm"
                                mt="xs"
                            />
                        )}
                    </Card>
                </Grid.Col>

                <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                    <Card withBorder>
                        <Group justify="space-between">
                            <div>
                                <Text size="sm" c="dimmed">Market Size</Text>
                                <Text size="xl" fw={700}>
                                    {localIdea.tam_sam_som?.tam ? `$${localIdea.tam_sam_som.tam}M` : 'TBD'}
                                </Text>
                            </div>
                            <IconChartLine size={24} color="var(--mantine-color-green-6)" />
                        </Group>
                    </Card>
                </Grid.Col>

                <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
                    <Card withBorder>
                        <Group justify="space-between">
                            <div>
                                <Text size="sm" c="dimmed">Sources</Text>
                                <Text size="xl" fw={700}>
                                    {localIdea.sources?.length || 0}
                                </Text>
                            </div>
                            <IconTrendingUp size={24} color="var(--mantine-color-purple-6)" />
                        </Group>
                    </Card>
                </Grid.Col>
            </Grid>

            {/* Main Content Tabs */}
            <Tabs value={activeTab} onChange={setActiveTab}>
                <Tabs.List>
                    <Tabs.Tab value="overview" leftSection={<IconBulb size={16} />}>
                        Overview
                    </Tabs.Tab>
                    <Tabs.Tab value="market" leftSection={<IconUsers size={16} />}>
                        Market & Users
                    </Tabs.Tab>
                    <Tabs.Tab value="product" leftSection={<IconRocket size={16} />}>
                        Product
                    </Tabs.Tab>
                    <Tabs.Tab value="business" leftSection={<IconChartLine size={16} />}>
                        Business Model
                    </Tabs.Tab>
                    <Tabs.Tab value="technical" leftSection={<IconCode size={16} />}>
                        Technical
                    </Tabs.Tab>
                    <Tabs.Tab value="risks" leftSection={<IconShield size={16} />}>
                        Risks & Compliance
                    </Tabs.Tab>
                </Tabs.List>

                {/* Overview Tab */}
                <Tabs.Panel value="overview" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 8 }}>
                            <Stack gap="md">
                                <Card withBorder>
                                    <Title order={3} mb="sm">Description</Title>
                                    {editMode ? (
                                        <Textarea
                                            value={localIdea.description}
                                            onChange={(e) => handleFieldUpdate('description', e.target.value)}
                                            minRows={3}
                                            autosize
                                        />
                                    ) : (
                                        <Text>{localIdea.description}</Text>
                                    )}
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Unique Value Proposition</Title>
                                    {editMode ? (
                                        <Textarea
                                            value={localIdea.uvp || ''}
                                            onChange={(e) => handleFieldUpdate('uvp', e.target.value)}
                                            minRows={2}
                                            autosize
                                        />
                                    ) : (
                                        <Text>{localIdea.uvp || 'Not defined'}</Text>
                                    )}
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Problem Statement</Title>
                                    {editMode ? (
                                        <Textarea
                                            value={localIdea.problem_statement || ''}
                                            onChange={(e) => handleFieldUpdate('problem_statement', e.target.value)}
                                            minRows={2}
                                            autosize
                                        />
                                    ) : (
                                        <Text>{localIdea.problem_statement || 'Not defined'}</Text>
                                    )}
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Solution Approach</Title>
                                    {editMode ? (
                                        <Textarea
                                            value={localIdea.solution_approach || ''}
                                            onChange={(e) => handleFieldUpdate('solution_approach', e.target.value)}
                                            minRows={2}
                                            autosize
                                        />
                                    ) : (
                                        <Text>{localIdea.solution_approach || 'Not defined'}</Text>
                                    )}
                                </Card>
                            </Stack>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 4 }}>
                            <Stack gap="md">
                                <Card withBorder>
                                    <Title order={4} mb="sm">Positioning</Title>
                                    <Text size="sm">{localIdea.positioning || 'Not defined'}</Text>
                                </Card>

                                <Card withBorder>
                                    <Title order={4} mb="sm">Target Segments</Title>
                                    <Stack gap="xs">
                                        {localIdea.target_segments?.map((segment, index) => (
                                            <Badge key={index} variant="light">{segment}</Badge>
                                        )) || <Text size="sm" c="dimmed">Not defined</Text>}
                                    </Stack>
                                </Card>

                                <Card withBorder>
                                    <Title order={4} mb="sm">Score Breakdown</Title>
                                    {localIdea.score_breakdown ? (
                                        <Stack gap="xs">
                                            {Object.entries(localIdea.score_breakdown).map(([key, value]) => (
                                                <Group key={key} justify="space-between">
                                                    <Text size="sm" tt="capitalize">{key.replace('_', ' ')}</Text>
                                                    <Badge size="sm" color={getScoreColor(value)}>
                                                        {value.toFixed(1)}
                                                    </Badge>
                                                </Group>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text size="sm" c="dimmed">Not available</Text>
                                    )}
                                </Card>
                            </Stack>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>

                {/* Market & Users Tab */}
                <Tabs.Panel value="market" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Ideal Customer Profiles</Title>
                                {localIdea.icps ? (
                                    <Stack gap="sm">
                                        {Object.entries(localIdea.icps).map(([key, value]) => (
                                            <div key={key}>
                                                <Text fw={500} tt="capitalize">{key}</Text>
                                                <Text size="sm" c="dimmed">{String(value)}</Text>
                                            </div>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">Not defined</Text>
                                )}
                            </Card>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Market Size (TAM/SAM/SOM)</Title>
                                {localIdea.tam_sam_som ? (
                                    <Stack gap="sm">
                                        {Object.entries(localIdea.tam_sam_som).map(([key, value]) => (
                                            <Group key={key} justify="space-between">
                                                <Text tt="uppercase">{key}</Text>
                                                <Text fw={500}>${value}M</Text>
                                            </Group>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">Not calculated</Text>
                                )}
                            </Card>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>

                {/* Product Tab */}
                <Tabs.Panel value="product" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">MVP Features</Title>
                                {localIdea.mvp_features?.length ? (
                                    <Stack gap="xs">
                                        {localIdea.mvp_features.map((feature, index) => (
                                            <Group key={index} gap="xs">
                                                <IconTarget size={16} color="var(--mantine-color-blue-6)" />
                                                <Text size="sm">{feature}</Text>
                                            </Group>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">Not defined</Text>
                                )}
                            </Card>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Product Roadmap</Title>
                                {localIdea.roadmap ? (
                                    <Stack gap="sm">
                                        {Object.entries(localIdea.roadmap).map(([phase, items]) => (
                                            <div key={phase}>
                                                <Text fw={500} tt="capitalize">{phase}</Text>
                                                <Text size="sm" c="dimmed">{String(items)}</Text>
                                            </div>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">Not defined</Text>
                                )}
                            </Card>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>

                {/* Business Model Tab */}
                <Tabs.Panel value="business" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Stack gap="md">
                                <Card withBorder>
                                    <Title order={3} mb="sm">Pricing Model</Title>
                                    <Text>{localIdea.pricing_model || 'Not defined'}</Text>
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Unit Economics</Title>
                                    {localIdea.unit_economics ? (
                                        <Stack gap="sm">
                                            {Object.entries(localIdea.unit_economics).map(([key, value]) => (
                                                <Group key={key} justify="space-between">
                                                    <Text tt="capitalize">{key.replace('_', ' ')}</Text>
                                                    <Text fw={500}>{String(value)}</Text>
                                                </Group>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text c="dimmed">Not calculated</Text>
                                    )}
                                </Card>
                            </Stack>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Stack gap="md">
                                <Card withBorder>
                                    <Title order={3} mb="sm">GTM Strategy</Title>
                                    {localIdea.gtm_strategy ? (
                                        <Stack gap="sm">
                                            {Object.entries(localIdea.gtm_strategy).map(([key, value]) => (
                                                <div key={key}>
                                                    <Text fw={500} tt="capitalize">{key.replace('_', ' ')}</Text>
                                                    <Text size="sm" c="dimmed">{String(value)}</Text>
                                                </div>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text c="dimmed">Not defined</Text>
                                    )}
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Channels</Title>
                                    {localIdea.channels?.length ? (
                                        <Stack gap="xs">
                                            {localIdea.channels.map((channel, index) => (
                                                <Badge key={index} variant="light">{channel}</Badge>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text c="dimmed">Not defined</Text>
                                    )}
                                </Card>
                            </Stack>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>

                {/* Technical Tab */}
                <Tabs.Panel value="technical" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Stack gap="md">
                                <Card withBorder>
                                    <Title order={3} mb="sm">Tech Stack</Title>
                                    {localIdea.tech_stack ? (
                                        <Stack gap="sm">
                                            {Object.entries(localIdea.tech_stack).map(([category, technologies]) => (
                                                <div key={category}>
                                                    <Text fw={500} tt="capitalize">{category.replace('_', ' ')}</Text>
                                                    <Group gap="xs" mt="xs">
                                                        {Array.isArray(technologies) ?
                                                            technologies.map((tech, index) => (
                                                                <Badge key={index} size="sm" variant="outline">{tech}</Badge>
                                                            )) :
                                                            <Text size="sm" c="dimmed">{String(technologies)}</Text>
                                                        }
                                                    </Group>
                                                </div>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text c="dimmed">Not defined</Text>
                                    )}
                                </Card>

                                <Card withBorder>
                                    <Title order={3} mb="sm">Build vs Buy</Title>
                                    {localIdea.build_vs_buy ? (
                                        <Stack gap="sm">
                                            {Object.entries(localIdea.build_vs_buy).map(([component, decision]) => (
                                                <Group key={component} justify="space-between">
                                                    <Text tt="capitalize">{component.replace('_', ' ')}</Text>
                                                    <Badge color={String(decision).toLowerCase() === 'build' ? 'blue' : 'green'}>
                                                        {String(decision)}
                                                    </Badge>
                                                </Group>
                                            ))}
                                        </Stack>
                                    ) : (
                                        <Text c="dimmed">Not analyzed</Text>
                                    )}
                                </Card>
                            </Stack>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Technical Risks</Title>
                                {localIdea.technical_risks?.length ? (
                                    <Stack gap="xs">
                                        {localIdea.technical_risks.map((risk, index) => (
                                            <Alert key={index} variant="light" color="yellow">
                                                <Text size="sm">{risk}</Text>
                                            </Alert>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">No risks identified</Text>
                                )}
                            </Card>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>

                {/* Risks & Compliance Tab */}
                <Tabs.Panel value="risks" pt="md">
                    <Grid>
                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Business Risks</Title>
                                {localIdea.risks ? (
                                    <Stack gap="sm">
                                        {Object.entries(localIdea.risks).map(([category, riskList]) => (
                                            <div key={category}>
                                                <Text fw={500} tt="capitalize">{category.replace('_', ' ')}</Text>
                                                {Array.isArray(riskList) ? (
                                                    <Stack gap="xs" mt="xs">
                                                        {riskList.map((risk, index) => (
                                                            <Alert key={index} variant="light" color="orange">
                                                                <Text size="sm">{risk}</Text>
                                                            </Alert>
                                                        ))}
                                                    </Stack>
                                                ) : (
                                                    <Text size="sm" c="dimmed" mt="xs">{String(riskList)}</Text>
                                                )}
                                            </div>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">No risks identified</Text>
                                )}
                            </Card>
                        </Grid.Col>

                        <Grid.Col span={{ base: 12, md: 6 }}>
                            <Card withBorder>
                                <Title order={3} mb="sm">Compliance Notes</Title>
                                {localIdea.compliance_notes?.length ? (
                                    <Stack gap="xs">
                                        {localIdea.compliance_notes.map((note, index) => (
                                            <Alert key={index} variant="light" color="blue">
                                                <Text size="sm">{note}</Text>
                                            </Alert>
                                        ))}
                                    </Stack>
                                ) : (
                                    <Text c="dimmed">No compliance requirements identified</Text>
                                )}
                            </Card>
                        </Grid.Col>
                    </Grid>
                </Tabs.Panel>
            </Tabs>

            {/* Citations Modal */}
            <Modal
                opened={showCitations}
                onClose={() => setShowCitations(false)}
                title="Sources & Citations"
                size="lg"
            >
                <Stack gap="md">
                    {localIdea.citations && Object.keys(localIdea.citations).length > 0 ? (
                        Object.entries(localIdea.citations).map(([source, citation]) => (
                            <div key={source}>
                                <Text fw={500} tt="capitalize">{source.replace('_', ' ')}</Text>
                                <Text size="sm" c="dimmed">{citation}</Text>
                            </div>
                        ))
                    ) : (
                        <Text c="dimmed">No citations available</Text>
                    )}

                    <Divider />

                    <div>
                        <Text fw={500} mb="xs">Data Sources ({localIdea.sources?.length || 0})</Text>
                        {localIdea.sources?.length ? (
                            <Text size="sm" c="dimmed">
                                Based on {localIdea.sources.length} market signals and data points
                            </Text>
                        ) : (
                            <Text size="sm" c="dimmed">No source data available</Text>
                        )}
                    </div>
                </Stack>
            </Modal>
        </Container>
    )
}
