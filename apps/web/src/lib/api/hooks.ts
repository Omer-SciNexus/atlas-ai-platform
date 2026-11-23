"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { getMe, listDocuments } from "./endpoints";
import type { DocumentPage, Permission } from "./types";

export const queryKeys = {
  me: ["me"] as const,
  documents: ["documents"] as const,
  search: (query: string) => ["search", query] as const,
  audit: ["audit-events"] as const,
};

export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: getMe, staleTime: 5 * 60_000 });
}

/**
 * Whether the signed-in user has a permission. This only decides what the page offers;
 * the API checks the permission again on every request.
 */
export function useCan(permission: Permission): boolean {
  return useMe().data?.permissions.includes(permission) ?? false;
}

function isBeingIngested(pages: DocumentPage[] | undefined): boolean {
  return (
    pages?.some((page) =>
      page.items.some((d) => d.status === "pending" || d.status === "processing"),
    ) ?? false
  );
}

export function useDocuments() {
  return useInfiniteQuery({
    queryKey: queryKeys.documents,
    queryFn: ({ pageParam }) => listDocuments(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Ingestion runs in the worker, so poll while a document is on its way to "ready".
    refetchInterval: (query) => (isBeingIngested(query.state.data?.pages) ? 2000 : false),
  });
}
