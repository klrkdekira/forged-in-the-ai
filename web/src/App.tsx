import { Button } from '@/components/ui/button'

export default function App() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center animate-in fade-in zoom-in duration-500">
      <h1 className="text-4xl md:text-6xl font-black tracking-tight text-foreground">
        Forged <span className="text-primary">AI</span>
      </h1>
      <p className="text-xl text-muted-foreground max-w-[600px]">
        A premium tabletop RPG engine for Forged in the Dark, powered by AI.
      </p>
      <div className="flex gap-4 mt-8">
        <Button type="button" size="lg">New Campaign</Button>
        <Button type="button" variant="outline" size="lg">
          Load Campaign
        </Button>
      </div>
    </div>
  )
}
