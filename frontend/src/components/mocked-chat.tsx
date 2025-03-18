import React, { useState } from "react";

const useChatMock = () => {
  const [messages, setMessages] = useState([
    { role: "user", content: "Olá, como você está?" },
    { role: "assistant", content: "Estou bem! Como posso ajudar?" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, newMessage]);
    setIsLoading(true);

    setTimeout(() => {
      const botResponse = { role: "assistant", content: `Resposta mockada para: ${input}` };
      setMessages((prev) => [...prev, botResponse]);
      setIsLoading(false);
    }, 1000);

    setInput("");
  };

  const reload = () => {
    setMessages([]);
  };

  return {
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    reload,
  };
};

export default useChatMock;
