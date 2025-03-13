import NavBar from "@/components/ui/home/navbar";

export default function HomeLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <>
            <NavBar />
            <div className="bg-background text-foreground w-full px-10 lg:px-30">
                {children}
            </div>
        </>
    );
}

