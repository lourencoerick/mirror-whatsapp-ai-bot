// src/components/inbox/inbox-item.tsx
/**
 * @fileoverview Represents a single inbox item in a list, displaying its
 * name, channel type, and providing action buttons.
 */
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Settings, Trash2 } from "lucide-react";
import React from "react";

import { components } from "@/types/api";
type Inbox = components["schemas"]["InboxRead"];

/**
 * Props accepted by the InboxItem component.
 */
interface InboxItemProps {
  /** The inbox data object to display. */
  inbox: Inbox;
  /** Optional handler function called when the configure button is clicked. */
  onConfigureClick?: (inboxId: string) => void;
  /** Optional handler function called when the delete button is clicked. */
  onDeleteClick?: (inboxId: string) => void;
  /** Optional handler function called when the main card area is clicked. */
  onCardClick?: (inboxId: string) => void;
}

/**
 * Renders a single Inbox item card with details and action buttons.
 * Uses Tailwind 'group' utility for hover effects on action buttons.
 *
 * @component
 * @param {InboxItemProps} props - The component props.
 * @returns {React.ReactElement} The rendered inbox item.
 */
export const InboxItem: React.FC<InboxItemProps> = ({
  inbox,
  onConfigureClick,
  onDeleteClick,
  onCardClick, // Added optional card click handler prop
}) => {
  /**
   * Handles the click event on the 'Configure' button.
   * Prevents event propagation to the parent card click handler.
   * Calls the `onConfigureClick` prop function if provided.
   * @param {React.MouseEvent<HTMLButtonElement>} e - The mouse event.
   */
  const handleConfigure = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Important: Prevent card click handler from firing
    if (onConfigureClick) {
      onConfigureClick(inbox.id);
    } else {
      console.warn("InboxItem: onConfigureClick handler not provided."); // Optional warning
    }
  };

  /**
   * Handles the click event on the 'Delete' button.
   * Prevents event propagation to the parent card click handler.
   * Calls the `onDeleteClick` prop function if provided.
   * @param {React.MouseEvent<HTMLButtonElement>} e - The mouse event.
   */
  const handleDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Important: Prevent card click handler from firing
    if (onDeleteClick) {
      onDeleteClick(inbox.id);
    } else {
      console.warn("InboxItem: onDeleteClick handler not provided."); // Optional warning
    }
  };

  /**
   * Handles the click event on the main card area.
   * Calls the `onCardClick` prop function if provided.
   * Useful for navigating to an inbox detail view.
   */
  const handleCardClick = () => {
    if (onCardClick) {
      onCardClick(inbox.id);
    } else {
      console.log("Card clicked for inbox:", inbox.id); // Default behavior if no handler
      // Example: Navigate to inbox detail/chat view
      // router.push(`/dashboard/inboxes/${inbox.id}/conversations`);
    }
  };

  // Determine if the card should be interactive based on whether a handler is provided
  const isCardClickable = !!onCardClick;

  return (
    <div
      onClick={isCardClickable ? handleCardClick : undefined} // Only attach handler if function provided
      className={`group flex items-center justify-between p-4 border rounded-lg bg-card text-card-foreground shadow-sm transition-colors ${
        isCardClickable ? "cursor-pointer hover:bg-muted/50" : "" // Apply hover styles only if clickable
      }`}
      role={isCardClickable ? "button" : undefined} // Add role="button" if clickable
      tabIndex={isCardClickable ? 0 : undefined} // Make it focusable if clickable
      aria-labelledby={`inbox-name-${inbox.id}`} // Point to the name for screen readers
      onKeyDown={
        isCardClickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") handleCardClick();
            }
          : undefined
      } // Keyboard activation
    >
      {/* Left Side: Name and Type */}
      <div className="flex flex-col gap-1 overflow-hidden mr-2">
        {" "}
        {/* Added overflow-hidden and margin */}
        <h3
          id={`inbox-name-${inbox.id}`} // ID for aria-labelledby
          className="font-semibold text-base leading-tight truncate" // Added truncate for long names
        >
          {inbox.name}
        </h3>
        <Badge variant="secondary" className="w-fit capitalize">
          {" "}
          {/* Added capitalize */}
          {inbox.channel_type.replace(/_/g, " ")}{" "}
          {/* Make channel type more readable */}
        </Badge>
      </div>

      {/* Right Side: Actions (visible on hover or focus-within) */}
      {/* Using group-hover and group-focus-within for better accessibility */}
      <div className="flex items-center gap-1 sm:gap-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-within:opacity-100 transition-opacity flex-shrink-0">
        {" "}
        {/* Added flex-shrink-0 */}
        {/* Configure Button */}
        {onConfigureClick && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleConfigure}
            aria-label={`Configure inbox ${inbox.name}`} // More descriptive label
          >
            <Settings className="h-4 w-4" />
          </Button>
        )}
        {/* Delete Button */}
        {onDeleteClick && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleDelete}
            className="text-destructive hover:text-destructive/90" // Adjusted hover color
            aria-label={`Delete inbox ${inbox.name}`} // More descriptive label
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
};
