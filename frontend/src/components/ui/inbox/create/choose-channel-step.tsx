/**
 * @fileoverview Step 1 Component for selecting the Inbox channel type.
 * Displays options like WhatsApp Evolution API and WhatsApp Cloud API.
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { components } from "@/types/api";
import { IconCloud, IconServer } from "@tabler/icons-react";
import React from "react";

// Usar o tipo do OpenAPI para garantir consistência
type ChannelTypeValue = components["schemas"]["ChannelTypeEnum"];

// Channel options definition with disabled flag
const channelOptions: Array<{
  id: ChannelTypeValue;
  name: string;
  description: string;
  icon: React.ElementType;
  disabled: boolean;
}> = [
  {
    id: "whatsapp_evolution",
    name: "WhatsApp (Evolution API)",
    description:
      "Conecte via Evolution API auto-hospedada (Requer escanear QR code).",
    icon: IconServer,
    disabled: false,
  },
  {
    id: "whatsapp_cloud",
    name: "WhatsApp (API Oficial Cloud)",
    description:
      "Conecte via API oficial Cloud da Meta (Requer configuração de App Meta).",
    icon: IconCloud,
    disabled: false,
  },
];

interface ChooseChannelStepProps {
  /** Function called when a channel is selected, passing the channel type ID. */
  onSelectChannel: (channelTypeId: ChannelTypeValue) => void; // Usar o tipo do enum
  stepTitle: string;
  stepDescription: string;
}

/**
 * Renders clickable cards to select the desired communication channel.
 * This is typically the first step in the Inbox creation wizard.
 * Disabled options are visually indicated and non-interactive.
 *
 * @param {ChooseChannelStepProps} props - Component props.
 * @returns {React.ReactElement} The channel selection component.
 */
export const ChooseChannelStep: React.FC<ChooseChannelStepProps> = ({
  onSelectChannel,
  stepTitle,
  stepDescription,
}) => {
  return (
    <TooltipProvider delayDuration={100}>
      <div className="space-y-6">
        <CardHeader className="p-0 mb-2 md:mb-4">
          <CardTitle className="text-xl md:text-2xl">{stepTitle}</CardTitle>
          <CardDescription>{stepDescription}</CardDescription>
        </CardHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
          {channelOptions.map((channel) => {
            const isDisabled = channel.disabled;

            const cardContent = (
              <Card
                key={channel.id}
                onClick={() => !isDisabled && onSelectChannel(channel.id)}
                className={cn(
                  "transition-all duration-150 ease-in-out",
                  isDisabled
                    ? "opacity-50 cursor-not-allowed border-border"
                    : "cursor-pointer hover:border-primary hover:shadow-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                )}
                role="button"
                tabIndex={isDisabled ? -1 : 0}
                onKeyDown={(e) => {
                  if (!isDisabled && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onSelectChannel(channel.id);
                  }
                }}
                aria-disabled={isDisabled}
                aria-label={`Selecionar canal ${channel.name}${
                  isDisabled ? " (Em breve)" : ""
                }`}
              >
                <CardHeader className="flex flex-row items-center gap-3 md:gap-4 pb-2 pt-4 px-4 md:px-5">
                  {channel.icon && (
                    <channel.icon
                      className={cn(
                        "h-7 w-7 md:h-8 md:w-8 flex-shrink-0",
                        isDisabled ? "text-muted-foreground" : "text-primary"
                      )}
                    />
                  )}
                  <CardTitle className="text-base md:text-lg">
                    {channel.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-4 px-4 md:px-5">
                  <p className="text-xs md:text-sm text-muted-foreground">
                    {channel.description}
                  </p>
                </CardContent>
              </Card>
            );

            return isDisabled ? (
              <Tooltip key={`${channel.id}-tooltip`}>
                <TooltipTrigger asChild>{cardContent}</TooltipTrigger>
                <TooltipContent>
                  <p>Em breve</p>
                </TooltipContent>
              </Tooltip>
            ) : (
              cardContent
            );
          })}
        </div>
      </div>
    </TooltipProvider>
  );
};
