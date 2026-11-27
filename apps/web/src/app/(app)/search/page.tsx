import type { Metadata } from "next";
import { Suspense } from "react";

import { SearchView } from "@/features/search/search-view";

export const metadata: Metadata = { title: "Search" };

export default function SearchPage() {
  // The view reads the query from the address, which is only known in the browser.
  return (
    <Suspense>
      <SearchView />
    </Suspense>
  );
}
