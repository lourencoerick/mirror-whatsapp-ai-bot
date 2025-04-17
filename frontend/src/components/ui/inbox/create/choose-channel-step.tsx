/**
 * @fileoverview Step 1 Component for selecting the Inbox channel type.
 * Displays options like WhatsApp Evolution API and WhatsApp Cloud API.
 */
import React from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"; // Import Tooltip components
import { cn } from '@/lib/utils'; // Import cn utility
// Consider adding specific icons if available
import { IconServer, IconCloud } from '@tabler/icons-react'; // Using Tabler icons as example

// Channel options definition with disabled flag
const channelOptions = [
    {
        id: 'whatsapp_evolution_api',
        name: 'WhatsApp (Evolution API)',
        description: 'Conecte via Evolution API auto-hospedada (Requer escanear QR code).',
        icon: IconServer,
        disabled: false, // Explicitly set as not disabled
    },
    {
        id: 'whatsapp_cloud_api',
        name: 'WhatsApp (API Oficial Cloud)',
        description: 'Conecte via API oficial Cloud da Meta (Requer configuração de App Meta).',
        icon: IconCloud,
        disabled: true, // *** Mark as disabled ***
    },
];

interface ChooseChannelStepProps {
    /** Function called when a channel is selected, passing the channel type ID. */
    onSelectChannel: (channelTypeId: string) => void;
    stepTitle: string;
    stepDescription: string;
}

/**
 * Renders clickable cards to select the desired communication channel.
 * This is typically the first step in the Inbox creation wizard.
 * Disabled options are visually indicated and non-interactive.
 *
 * @component
 * @param {ChooseChannelStepProps} props - Component props.
 * @returns {React.ReactElement} The channel selection component.
 */
export const ChooseChannelStep: React.FC<ChooseChannelStepProps> = ({
    onSelectChannel,
    stepTitle,
    stepDescription
}) => {
    return (
        <TooltipProvider delayDuration={100}> {/* Provider for tooltips */}
            <div className="space-y-6">
                {/* Step Header */}
                <CardHeader className="p-0 mb-2 md:mb-4">
                    <CardTitle className="text-xl md:text-2xl">{stepTitle}</CardTitle>
                    <CardDescription>{stepDescription}</CardDescription>
                </CardHeader>

                {/* Grid with Channel Options */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                    {channelOptions.map((channel) => {
                        const isDisabled = channel.disabled; // Check disabled state

                        const cardContent = (
                            <Card
                                key={channel.id}
                                onClick={() => !isDisabled && onSelectChannel(channel.id)} // Prevent click if disabled
                                className={cn(
                                    "transition-all duration-150 ease-in-out",
                                    isDisabled
                                        ? "opacity-50 cursor-not-allowed border-border" // Disabled styles
                                        : "cursor-pointer hover:border-primary hover:shadow-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" // Enabled styles
                                )}
                                role="button"
                                tabIndex={isDisabled ? -1 : 0} // Remove from tab order if disabled
                                onKeyDown={(e) => {
                                    if (!isDisabled && (e.key === 'Enter' || e.key === ' ')) {
                                        e.preventDefault();
                                        onSelectChannel(channel.id);
                                    }
                                }} // Prevent keydown if disabled
                                aria-disabled={isDisabled} // Indicate disabled state for accessibility
                                aria-label={`Selecionar canal ${channel.name}${isDisabled ? ' (Em breve)' : ''}`}
                            >
                                <CardHeader className="flex flex-row items-center gap-3 md:gap-4 pb-2 pt-4 px-4 md:px-5">
                                    {channel.icon && <channel.icon className={cn("h-7 w-7 md:h-8 md:w-8 flex-shrink-0", isDisabled ? "text-muted-foreground" : "text-primary")} />}
                                    <CardTitle className="text-base md:text-lg">{channel.name}</CardTitle>
                                </CardHeader>
                                <CardContent className="pb-4 px-4 md:px-5">
                                    <p className="text-xs md:text-sm text-muted-foreground">
                                        {channel.description}
                                        {/* Optionally add 'Em breve' text directly */}
                                        {/* {isDisabled && <span className="ml-1 font-semibold">(Em breve)</span>} */}
                                    </p>
                                </CardContent>
                            </Card>
                        );

                        // Wrap with Tooltip only if disabled
                        return isDisabled ? (
                            <Tooltip key={`${channel.id}-tooltip`}>
                                <TooltipTrigger asChild>{cardContent}</TooltipTrigger>
                                <TooltipContent>
                                    <p>Em breve</p>
                                </TooltipContent>
                            </Tooltip>
                        ) : (
                            cardContent // Render card directly if not disabled
                        );
                    })}
                </div>
            </div>
        </TooltipProvider>
    );
};