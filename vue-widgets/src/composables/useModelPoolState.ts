import { ref, watch, toRaw } from 'vue'
import { useModelPoolApi } from './useModelPoolApi'
import type {
  BaseModelOption,
  TagOption,
  FolderTreeNode,
  LoraItem as ModelItem, // Alias LoraItem to ModelItem
  ComponentWidget,
  ModelPoolConfig // Use ModelPoolConfig
} from './types'

export function useModelPoolState(widget: ComponentWidget<ModelPoolConfig>) {
  const api = useModelPoolApi()

  // Flag to prevent infinite loops during config restoration
  // callback → restoreFromConfig → watch → refreshPreview → buildConfig → widget.value = config → callback → ...
  let isUpdatingFromConfig = false

  // --- Filter State ---
  const selectedBaseModels = ref<string[]>([])
  const includeTags = ref<string[]>([])
  const excludeTags = ref<string[]>([])
  const includeFolders = ref<string[]>([])
  const excludeFolders = ref<string[]>([])
  const noCreditRequired = ref(false)
  const allowSelling = ref(false)

  // Available options from API
  const availableBaseModels = ref<BaseModelOption[]>([])
  const availableTags = ref<TagOption[]>([])
  const folderTree = ref<FolderTreeNode[]>([])

  // --- Preview State ---
  const previewItems = ref<ModelItem[]>([])
  const matchCount = ref(0)
  const isPreviewStale = ref(false)
  const isLoading = api.isLoading // Direct assignment, assuming api.isLoading is a Ref<boolean>

  // Build configuration object for widget
  const buildConfig = (): ModelPoolConfig => {
    return {
      version: 1,
      filters: {
        baseModels: [...selectedBaseModels.value],
        tags: {
          include: [...includeTags.value],
          exclude: [...excludeTags.value]
        },
        folders: {
          include: [...includeFolders.value],
          exclude: [...excludeFolders.value]
        },
        favoritesOnly: false, // For future implementation
        license: {
          noCreditRequired: noCreditRequired.value,
          allowSelling: allowSelling.value
        }
      },
      preview: {
        matchCount: matchCount.value,
        lastUpdated: Date.now()
      }
    }
  }

  // Update widget value (this triggers callback for UI sync)
  const updateWidgetValue = () => {
    // Skip during restoration to prevent infinite loops:
    // callback → restoreFromConfig → watch → refreshPreview → buildConfig → widget.value = config → callback → ...
    if (!isUpdatingFromConfig) {
      widget.value = buildConfig()
    }
  }

  // Restore state from configuration object
  const restoreFromConfig = (config: ModelPoolConfig) => {
    if (!config?.filters) return

    // Prevent watcher from triggering API calls during restoration
    isUpdatingFromConfig = true

    try {
      const { filters } = config

      selectedBaseModels.value = [...(filters.baseModels || [])]
      includeTags.value = [...(filters.tags?.include || [])]
      excludeTags.value = [...(filters.tags?.exclude || [])]
      includeFolders.value = [...(filters.folders?.include || [])]
      excludeFolders.value = [...(filters.folders?.exclude || [])]
      noCreditRequired.value = filters.license?.noCreditRequired || false
      allowSelling.value = filters.license?.allowSelling || false

      // We don't restore preview state, we let the watch trigger a fresh fetch
      // after restoration is complete
    } finally {
      // Must use nextTick or timeout to ensure watchers don't fire immediately
      // before we release the flag
      setTimeout(() => {
        isUpdatingFromConfig = false
      }, 0)
    }
  }

  // Fetch filter options (base models, tags, folders)
  const fetchFilterOptions = async () => {
    try {
      const [models, tags, folders] = await Promise.all([
        api.fetchBaseModels(),
        api.fetchTags(),
        api.fetchFolderTree()
      ])

      availableBaseModels.value = models.filter(m => m.name !== 'unknown')
      availableTags.value = tags.filter(t => t.name !== 'unknown')
      folderTree.value = folders
    } catch (error) {
      console.error('[ModelPoolState] Failed to fetch filter options:', error)
    }
  }

  // Refresh preview models based on current filters
  const refreshPreview = async () => {
    if (isUpdatingFromConfig) return

    try {
      const result = await api.fetchModels({
        baseModels: selectedBaseModels.value,
        tagsInclude: includeTags.value,
        tagsExclude: excludeTags.value,
        foldersInclude: includeFolders.value,
        foldersExclude: excludeFolders.value,
        noCreditRequired: noCreditRequired.value,
        allowSelling: allowSelling.value,
        page: 1,
        pageSize: 6 // Match LoraPoolSummaryView display
      })

      previewItems.value = result.items
      matchCount.value = result.total
      isPreviewStale.value = false

      updateWidgetValue()
    } catch (error) {
      console.error('[ModelPoolState] Failed to refresh preview:', error)
    }
  }

  // Debounced filter change handler
  let filterTimeout: ReturnType<typeof setTimeout> | null = null
  const onFilterChange = () => {
    if (filterTimeout) clearTimeout(filterTimeout)
    filterTimeout = setTimeout(() => {
      refreshPreview()
    }, 300)
  }

  // Watch all filter changes
  watch([
    selectedBaseModels,
    includeTags,
    excludeTags,
    includeFolders,
    excludeFolders,
    noCreditRequired,
    allowSelling
  ], onFilterChange, { deep: true })

  return {
    // Filter state
    selectedBaseModels,
    includeTags,
    excludeTags,
    includeFolders,
    excludeFolders,
    noCreditRequired,
    allowSelling,

    // Available options
    availableBaseModels,
    availableTags,
    folderTree,

    // Preview state
    previewItems,
    matchCount,
    isLoading,

    // Actions
    buildConfig,
    restoreFromConfig,
    fetchFilterOptions,
    refreshPreview
  }
}

export type LoraPoolStateReturn = ReturnType<typeof useLoraPoolState>
