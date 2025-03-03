"use client";

import { cn } from "@/lib/utils";
import { AnimatedList } from "@/components/magicui/animated-list";

interface Item {
  name: string;
  description: string;
  icon: string;
  color: string;
  time: string;
}

let notifications = [
    {
      name: "New message",
      description: "João: 'Tem tamanho M disponível?'",
      time: "1m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Maria: 'Oi, ainda tem estoque?'",
      time: "2m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Carlos: 'Qual o prazo de entrega para SP?'",
      time: "3m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Ana: 'Vocês aceitam PIX?'",
      time: "4m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Pedro: 'Estou tentando comprar, mas o site tá travando.'",
      time: "5m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Lucas: 'Desconto para pagamento à vista?'",
      time: "6m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Fernanda: 'Quero comprar 3 unidades, tem frete grátis?'",
      time: "7m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Ricardo: 'Preciso de um atendimento urgente!'",
      time: "8m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Tatiane: 'Me responde, por favor! 😢'",
      time: "9m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Bruno: 'Quais são as formas de pagamento?'",
      time: "10m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Camila: 'Tem mais fotos do produto?'",
      time: "11m ago",
      icon: "💬",
      color: "#00C9A7",
    },
    {
      name: "New message",
      description: "Diego: 'Quero comprar, mas preciso tirar uma dúvida antes.'",
      time: "12m ago",
      icon: "💬",
      color: "#00C9A7",
    },
  ];
  

notifications = Array.from({ length: 10 }, () => notifications).flat();

const Notification = ({ name, description, icon, color, time }: Item) => {
  return (
    <figure
      className={cn(
        "relative mx-auto min-h-fit w-full max-w-[400px] cursor-pointer overflow-hidden rounded-2xl p-4",
        // animation styles
        "transition-all duration-200 ease-in-out hover:scale-[103%]",
        // light styles
        "bg-white [box-shadow:0_0_0_1px_rgba(0,0,0,.03),0_2px_4px_rgba(0,0,0,.05),0_12px_24px_rgba(0,0,0,.05)]",
        // dark styles
        "transform-gpu dark:bg-transparent dark:backdrop-blur-md dark:[border:1px_solid_rgba(255,255,255,.1)] dark:[box-shadow:0_-20px_80px_-20px_#ffffff1f_inset]",
      )}
    >
      <div className="flex flex-row items-center gap-3">
        <div
          className="flex size-10 items-center justify-center rounded-2xl"
          style={{
            backgroundColor: color,
          }}
        >
          <span className="text-lg">{icon}</span>
        </div>
        <div className="flex flex-col overflow-hidden">
          <figcaption className="flex flex-row items-center whitespace-pre text-lg font-medium dark:text-white ">
            <span className="text-sm sm:text-lg">{name}</span>
            <span className="mx-1">·</span>
            <span className="text-xs text-gray-500">{time}</span>
          </figcaption>
          <p className="text-sm font-normal dark:text-white/60">
            {description}
          </p>
        </div>
      </div>
    </figure>
  );
};

export function AnimatedListDemo({
  className,
}: {
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex h-[500px] w-full flex-col overflow-hidden p-2",
        className,
      )}
    >
      <AnimatedList>
        {notifications.map((item, idx) => (
          <Notification {...item} key={idx} />
        ))}
      </AnimatedList>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-background"></div>
    </div>
  );
}
