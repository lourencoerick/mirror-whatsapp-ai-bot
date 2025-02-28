// components/ButtonWithIcon.tsx
import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"
import React from "react"

type ButtonProps = React.ComponentProps<typeof Button>

interface ButtonWithIconProps extends ButtonProps {
  // Optionally, allow an icon override
  icon?: React.ReactNode
}

export function ButtonWithIcon({ children, icon, className = "", ...props }: ButtonWithIconProps) {
  return (
    <Button {...props} className={`flex items-center space-x-2 ${className}`}>
      <span>{children}</span>
      {icon}
    </Button>
  )
}

export function ExperimentButton({ children, className = "", ...props }: ButtonWithIconProps) {
  return (
    <Button {...props} className={`flex items-center space-x-2 ${className}`}>
      <span>{children}</span>
      <ArrowRight className="h-6 w-6" />
    </Button>
  )
}
