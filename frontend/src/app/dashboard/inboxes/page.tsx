/**
 * @fileoverview Page component for displaying the list of user inboxes.
 * Sets the main layout header title to "Inboxes".
 */
"use client";

import React, { useEffect } from 'react';
import { InboxList } from '@/components/ui/inbox/inbox-list';
import { useLayoutContext } from '@/contexts/layout-context';

/**
 * Renders the main page for managing Inboxes.
 * Displays the list of inboxes and sets the appropriate page title.
 *
 * @component
 * @returns {React.ReactElement} The inboxes page component.
 */
export default function InboxesPage() {
  const { setPageTitle } = useLayoutContext();

  useEffect(() => {
    setPageTitle("Inboxes");
    return () => {
      setPageTitle("Dashboard");
    };
  }, [setPageTitle]);

  return (
    <InboxList />
  );
}