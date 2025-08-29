'use client'

import { useState, useCallback, useEffect } from 'react'
import {
    TextInput,
    Button,
    Group,
    Stack,
    Card,
    Text,
    Badge,
    ActionIcon,
    Tooltip,
    Select,
    MultiSelect,
    NumberInput,
    Collapse,
    Divider,
    Loader,
    Alert,
    Anchor,
    Progress,
    Grid,
    Title
} from '@mantine/core'
import {
    IconSearch,
    IconFilter,
    IconExternalLink,
    IconTrendingUp,
    IconCalendar,
    IconSource,
    IconBrain,
    IconTarget,
    IconChevronDown,
    IconChevronUp
} from '@tabler/icons-react'
import { useDebouncedValue } from '@mantine/hooks'

interface SearchResult {
    id: string
    title: string
    content: string
    source: string
    url?: string
    entities: {
        industries?: string[]
        technologies?: string[]
        companies?: string[]
        monetization_models?: string[]
    }
    metadata: Record<string, any>
    created_at: string
    published_at?: string
    search_score: number
    search_method: string
    score_breakdown: {
        bm25: number
        vector: number
        rerank: number
        combined: number
        final: number
    }
}

interface SearchFilters {
    sources?: string[]
    industries?: string[]
    date_range?: {
        from?: string
        to?: string
    }
    min_score?: number
}

interface HybridSearchProps {
    onResultSelect?: (result: SearchResult) => void
    onSearchComplete?: (results: SearchResult[], query: string) => void
    placeholder?: string
    showFilters?: boolean
    autoSearch?: boolean
}

export function HybridSearch({
    onResultSelect,
    onSearchComplete,
    placeholder = "Search market signals, trends, and opportunities...",
    showFilters = true,
    autoSearch = false
}: HybridSearchProps) {
    const [query, setQuery] = useState('')
    const [debouncedQuery] = useDebouncedValue(query, 500)
    const [results, setResults] = useState<SearchResult[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)

    // Filters
    const [filters, setFilters] = useState<SearchFilters>({})
    const [availableSources] = useState([
        'product_hunt', 'github', 'rss', 'crunchbase', 'google_trends'
    ])
    const [availableIndustries] = useState([
        'software', 'ai_ml', 'fintech', 'healthcare', 'ecommerce',
        'gaming', 'education', 'productivity', 'security', 'iot'
    ])

    // Search function
    const performSearch = useCallback(async (searchQuery: string, searchFilters: SearchFilters = {}) => {
        if (!searchQuery.trim()) {
            setResults([])
            return
        }

        setLoading(true)
        setError(null)

        try {
            const response = await fetch('/api/v1/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: searchQuery,
                    filters: searchFilters,
                    limit: 20,
                    hybrid_weights: {
                        bm25: 0.4,
                        vector: 0.4,
                        rerank: 0.2
                    }
                })
            })

            if (!response.ok) {
                throw new Error('Search failed')
            }

            const data = await response.json()
            setResults(data.results || [])
            onSearchComplete?.(data.results || [], searchQuery)

        } catch (err) {
            setError(err instanceof Error ? err.message : 'Search failed')
            setResults([])
        } finally {
            setLoading(false)
        }
    }, [onSearchComplete])

    // Auto-search on query change
    useEffect(() => {
        if (autoSearch && debouncedQuery) {
            performSearch(debouncedQuery, filters)
        }
    }, [debouncedQuery, filters, autoSearch, performSearch])

    const handleSearch = () => {
        performSearch(query, filters)
    }

    const handleKeyPress = (event: React.KeyboardEvent) => {
        if (event.key === 'Enter') {
            handleSearch()
        }
    }

    const getScoreColor = (score: number) => {
        if (score >= 0.8) return 'green'
        if (score >= 0.6) return 'yellow'
        if (score >= 0.4) return 'orange'
        return 'red'
    }

    const getMethodColor = (method: string) => {
        switch (method) {
            case 'hybrid': return 'blue'
            case 'bm25': return 'cyan'
            case 'vector': return 'purple'
            default: return 'gray'
        }
    }

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        })
    }

    return (
        <Stack gap="md">
            {/* Search Input */}
            <Group gap="xs">
                <TextInput
                    flex={1}
                    placeholder={placeholder}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyPress={handleKeyPress}
                    leftSection={<IconSearch size={16} />}
                    rightSection={loading ? <Loader size={16} /> : null}
                />
                <Button
                    onClick={handleSearch}
                    disabled={!query.trim() || loading}
                    leftSection={<IconSearch size={16} />}
                >
                    Search
                </Button>
                {showFilters && (
                    <Tooltip label="Advanced Filters">
                        <ActionIcon
                            variant={showAdvancedFilters ? 'filled' : 'light'}
                            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                        >
                            <IconFilter size={16} />
                        </ActionIcon>
                    </Tooltip>
                )}
            </Group>

            {/* Advanced Filters */}
            {showFilters && (
                <Collapse in={showAdvancedFilters}>
                    <Card withBorder>
                        <Stack gap="md">
                            <Group grow>
                                <MultiSelect
                                    label="Sources"
                                    placeholder="Filter by data sources"
                                    data={availableSources.map(s => ({ value: s, label: s.replace('_', ' ').toUpperCase() }))}
                                    value={filters.sources || []}
                                    onChange={(value) => setFilters(prev => ({ ...prev, sources: value }))}
                                />
                                <MultiSelect
                                    label="Industries"
                                    placeholder="Filter by industries"
                                    data={availableIndustries.map(i => ({ value: i, label: i.replace('_', ' ').toUpperCase() }))}
                                    value={filters.industries || []}
                                    onChange={(value) => setFilters(prev => ({ ...prev, industries: value }))}
                                />
                            </Group>

                            <Group grow>
                                <TextInput
                                    label="Date From"
                                    type="date"
                                    value={filters.date_range?.from || ''}
                                    onChange={(e) => setFilters(prev => ({
                                        ...prev,
                                        date_range: { ...prev.date_range, from: e.target.value }
                                    }))}
                                />
                                <TextInput
                                    label="Date To"
                                    type="date"
                                    value={filters.date_range?.to || ''}
                                    onChange={(e) => setFilters(prev => ({
                                        ...prev,
                                        date_range: { ...prev.date_range, to: e.target.value }
                                    }))}
                                />
                                <NumberInput
                                    label="Min Score"
                                    placeholder="0.0 - 1.0"
                                    min={0}
                                    max={1}
                                    step={0.1}
                                    value={filters.min_score}
                                    onChange={(value) => setFilters(prev => ({ ...prev, min_score: Number(value) }))}
                                />
                            </Group>

                            <Group>
                                <Button
                                    variant="light"
                                    size="sm"
                                    onClick={() => setFilters({})}
                                >
                                    Clear Filters
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleSearch}
                                    disabled={!query.trim()}
                                >
                                    Apply Filters
                                </Button>
                            </Group>
                        </Stack>
                    </Card>
                </Collapse>
            )}

            {/* Error Alert */}
            {error && (
                <Alert color="red" title="Search Error">
                    {error}
                </Alert>
            )}

            {/* Search Results */}
            <Stack gap="sm">
                {results.length > 0 && (
                    <Group justify="space-between">
                        <Text size="sm" c="dimmed">
                            Found {results.length} results for "{query}"
                        </Text>
                        <Group gap="xs">
                            <Text size="xs" c="dimmed">Sort by:</Text>
                            <Select
                                size="xs"
                                data={[
                                    { value: 'relevance', label: 'Relevance' },
                                    { value: 'date', label: 'Date' },
                                    { value: 'score', label: 'Score' }
                                ]}
                                defaultValue="relevance"
                                w={100}
                            />
                        </Group>
                    </Group>
                )}

                {results.map((result) => (
                    <Card
                        key={result.id}
                        withBorder
                        style={{ cursor: onResultSelect ? 'pointer' : 'default' }}
                        onClick={() => onResultSelect?.(result)}
                    >
                        <Stack gap="sm">
                            {/* Header */}
                            <Group justify="space-between" align="flex-start">
                                <div style={{ flex: 1 }}>
                                    <Group gap="xs" mb="xs">
                                        <Text fw={500} lineClamp={2}>
                                            {result.title}
                                        </Text>
                                        {result.url && (
                                            <Tooltip label="Open source">
                                                <ActionIcon
                                                    size="sm"
                                                    variant="subtle"
                                                    component="a"
                                                    href={result.url}
                                                    target="_blank"
                                                    onClick={(e) => e.stopPropagation()}
                                                >
                                                    <IconExternalLink size={12} />
                                                </ActionIcon>
                                            </Tooltip>
                                        )}
                                    </Group>

                                    <Text size="sm" c="dimmed" lineClamp={3}>
                                        {result.content}
                                    </Text>
                                </div>

                                <Stack gap="xs" align="flex-end">
                                    <Badge color={getScoreColor(result.search_score)} size="sm">
                                        {(result.search_score * 100).toFixed(0)}%
                                    </Badge>
                                    <Badge color={getMethodColor(result.search_method)} size="xs" variant="light">
                                        {result.search_method}
                                    </Badge>
                                </Stack>
                            </Group>

                            {/* Metadata */}
                            <Group gap="xs" wrap="wrap">
                                <Badge leftSection={<IconSource size={12} />} variant="outline" size="xs">
                                    {result.source.replace('_', ' ').toUpperCase()}
                                </Badge>

                                <Badge leftSection={<IconCalendar size={12} />} variant="outline" size="xs">
                                    {formatDate(result.published_at || result.created_at)}
                                </Badge>

                                {result.entities.industries?.slice(0, 2).map((industry) => (
                                    <Badge key={industry} color="blue" variant="light" size="xs">
                                        {industry.replace('_', ' ').toUpperCase()}
                                    </Badge>
                                ))}

                                {result.entities.technologies?.slice(0, 2).map((tech) => (
                                    <Badge key={tech} color="green" variant="light" size="xs">
                                        {tech}
                                    </Badge>
                                ))}
                            </Group>

                            {/* Score Breakdown */}
                            <Collapse in={false}>
                                <Divider my="xs" />
                                <Grid>
                                    <Grid.Col span={6}>
                                        <Text size="xs" c="dimmed">BM25: {result.score_breakdown.bm25.toFixed(2)}</Text>
                                        <Progress value={result.score_breakdown.bm25 * 100} size="xs" color="cyan" />
                                    </Grid.Col>
                                    <Grid.Col span={6}>
                                        <Text size="xs" c="dimmed">Vector: {result.score_breakdown.vector.toFixed(2)}</Text>
                                        <Progress value={result.score_breakdown.vector * 100} size="xs" color="purple" />
                                    </Grid.Col>
                                </Grid>
                            </Collapse>
                        </Stack>
                    </Card>
                ))}

                {/* Empty State */}
                {!loading && results.length === 0 && query && (
                    <Card withBorder>
                        <Stack align="center" py="xl">
                            <IconSearch size={48} color="var(--mantine-color-gray-5)" />
                            <Text c="dimmed">No results found for "{query}"</Text>
                            <Text size="sm" c="dimmed" ta="center">
                                Try adjusting your search terms or filters
                            </Text>
                        </Stack>
                    </Card>
                )}

                {/* Loading State */}
                {loading && (
                    <Card withBorder>
                        <Group justify="center" py="xl">
                            <Loader />
                            <Text c="dimmed">Searching...</Text>
                        </Group>
                    </Card>
                )}
            </Stack>
        </Stack>
    )
}
