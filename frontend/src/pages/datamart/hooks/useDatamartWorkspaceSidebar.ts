/**
 * Shared sidebar data and handlers for datamart chat + template routes.
 */
import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { NavigateFunction } from 'react-router-dom'
import { datamartService } from '../../../services/datamartService'
import type { DatamartSidebarProps } from '../components/DatamartSidebar'
import { navigateToNewChat } from '../lib/chatSessionRoute'
import { warmTemplateWorkspace } from '../lib/templateNavigation'

function pendingDeleteId(mutation: { isPending: boolean; variables?: string }): string | null {
  return mutation.isPending && mutation.variables != null ? mutation.variables : null
}

export interface UseDatamartWorkspaceSidebarOptions {
  activeSessionId: string | null
  activeTemplateId: string | null
  navigate: NavigateFunction
  onSessionDeleted?: () => void
}

export function useDatamartWorkspaceSidebar({
  activeSessionId,
  activeTemplateId,
  navigate,
  onSessionDeleted,
}: UseDatamartWorkspaceSidebarOptions): DatamartSidebarProps {
  const queryClient = useQueryClient()

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['datamart-sessions'],
    queryFn: () => datamartService.listSessions(),
    staleTime: 30000,
  })

  const { data: groupsData } = useQuery({
    queryKey: ['datamart-session-groups'],
    queryFn: () => datamartService.listSessionGroups(),
    staleTime: 60000,
  })

  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['datamart-templates'],
    queryFn: () => datamartService.listTemplates(),
    staleTime: 30000,
  })

  const { data: templateGroupsData } = useQuery({
    queryKey: ['datamart-template-groups'],
    queryFn: () => datamartService.listTemplateGroups(),
    staleTime: 60000,
  })

  const invalidateSessions = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['datamart-sessions'] })
  }, [queryClient])

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => datamartService.renameSession(id, title),
    onSuccess: invalidateSessions,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => datamartService.deleteSession(id),
    onSuccess: (_, deletedId) => {
      invalidateSessions()
      if (activeSessionId === deletedId) {
        onSessionDeleted?.()
        navigate('/datamart/chat')
      }
    },
  })

  const createGroupMutation = useMutation({
    mutationFn: (name: string) => datamartService.createSessionGroup(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-session-groups'] }),
  })

  const renameGroupMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => datamartService.renameSessionGroup(id, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-session-groups'] }),
  })

  const deleteGroupMutation = useMutation({
    mutationFn: (id: string) => datamartService.deleteSessionGroup(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-session-groups'] }),
  })

  const createTemplateGroupMutation = useMutation({
    mutationFn: (name: string) => datamartService.createTemplateGroup(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-template-groups'] }),
  })

  const renameTemplateGroupMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => datamartService.renameTemplateGroup(id, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-template-groups'] }),
  })

  const deleteTemplateGroupMutation = useMutation({
    mutationFn: (id: string) => datamartService.deleteTemplateGroup(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-template-groups'] }),
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: (id: string) => datamartService.deleteTemplate(id),
    onSuccess: (_, deletedId) => {
      void queryClient.invalidateQueries({ queryKey: ['datamart-templates'] })
      if (activeTemplateId === deletedId) {
        navigate('/datamart/chat')
      }
    },
  })

  const pinTemplateMutation = useMutation({
    mutationFn: (id: string) => datamartService.pinTemplate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datamart-templates'] }),
  })

  return {
    sessions: sessionsData?.sessions ?? [],
    activeSessionId,
    sessionsLoading,
    onWarmSession: (id: string) => {
      void queryClient.prefetchQuery({
        queryKey: ['datamart-session-messages', id, 1],
        queryFn: () => datamartService.getSessionMessages(id, 1, 5),
      })
    },
    onNewSession: () => navigateToNewChat(navigate),
    onRenameSession: (id, title) => renameMutation.mutate({ id, title }),
    onDeleteSession: (id) => deleteMutation.mutate(id),
    onMoveSessionToGroup: (sessionId, groupId) => {
      void datamartService.moveSessionToGroup(sessionId, groupId).then(invalidateSessions)
    },
    sessionGroups: groupsData?.groups ?? [],
    onCreateSessionGroup: (name) => createGroupMutation.mutate(name),
    onRenameSessionGroup: (id, name) => renameGroupMutation.mutate({ id, name }),
    onDeleteSessionGroup: (id) => deleteGroupMutation.mutate(id),
    templates: templatesData?.templates ?? [],
    activeTemplateId,
    templatesLoading,
    onWarmTemplate: (id: string) => warmTemplateWorkspace(queryClient, id),
    onDeleteTemplate: (id) => deleteTemplateMutation.mutate(id),
    onPinTemplate: (id) => pinTemplateMutation.mutate(id),
    onMoveTemplateToGroup: (templateId, groupId) => {
      void datamartService.moveTemplateToGroup(templateId, groupId).then(() =>
        queryClient.invalidateQueries({ queryKey: ['datamart-templates'] }),
      )
    },
    templateGroups: templateGroupsData?.groups ?? [],
    onCreateTemplateGroup: (name) => createTemplateGroupMutation.mutate(name),
    onRenameTemplateGroup: (id, name) => renameTemplateGroupMutation.mutate({ id, name }),
    onDeleteTemplateGroup: (id) => deleteTemplateGroupMutation.mutate(id),
    deletingSessionId: pendingDeleteId(deleteMutation),
    deletingTemplateId: pendingDeleteId(deleteTemplateMutation),
    deletingSessionGroupId: pendingDeleteId(deleteGroupMutation),
    deletingTemplateGroupId: pendingDeleteId(deleteTemplateGroupMutation),
  }
}
