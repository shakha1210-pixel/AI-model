import { createFileRoute } from '@tanstack/react-router'
import { ArrowDown, ArrowDownRight, ArrowUpRight, Braces, Check, Circle, Github, Layers3, Mail, Menu, MoveUpRight, Sparkles, X } from 'lucide-react'
import { useState } from 'react'

const profile = 'https://github.com/shakha1210-pixel'
const projects = [
  {
    number: '01', title: 'Apeiron', subtitle: 'AI workspace', color: 'violet', mark: 'A',
    description: 'A workspace foundation for connecting model providers and shaping configurable agents—built incrementally, with a clear line between what works today and what remains a roadmap.',
    status: 'Active development',
    details: ['Provider registry & adapters', 'Encrypted credential storage', 'Agent configuration builder', 'Single-turn text generation'],
    stack: 'FastAPI · SQLAlchemy · Pydantic · HTTPX · Vanilla JS',
    href: 'https://github.com/shakha1210-pixel/AI-model',
  },
  {
    number: '02', title: 'Nexus', subtitle: 'AI terminal for Ollama', color: 'blue', mark: 'N',
    description: 'A local-first AI workspace bringing model connections, conversations and scoped workspace tools into one desktop-oriented experience.',
    status: 'Active development',
    details: ['Ollama & OpenAI-compatible providers', 'Streaming chat & conversation history', 'Workspace explorer', 'Initial permission-scoped agent runtime'],
    stack: 'FastAPI · React 18 · TypeScript · Vite · PyWebView',
    href: 'https://github.com/shakha1210-pixel/Nexus-AI-Terminal-for-Ollama',
  },
  {
    number: '03', title: 'Logic-Hub', subtitle: 'Modular JavaScript', color: 'amber', mark: 'L',
    description: 'A hypercasual game project and an exploration of how distinct systems can stay understandable when their responsibilities are separated.',
    status: 'Independent project',
    details: ['Achievement engine', 'Challenge engine', 'Event engine', 'Core & ranking systems'],
    stack: 'JavaScript',
    href: 'https://github.com/shakha1210-pixel/Logic-Hub',
  },
]
const capabilities = [
  ['01', 'Product development', 'Turning broad product ideas into focused, staged work.'],
  ['02', 'AI-assisted engineering', 'Coordinating AI tools and reviewing their output with intent.'],
  ['03', 'Application architecture', 'Mapping modules, dependencies, interfaces, and data flow.'],
  ['04', 'Frontend development', 'Building responsive experiences and exploring interaction design.'],
  ['05', 'Backend foundations', 'Working across APIs, providers, persistence, and application boundaries.'],
  ['06', 'Research & validation', 'Following tests, investigating failures, and exploring real user flows.'],
]
const principles = ['Build with purpose.', 'Understand architecture, not just interfaces.', 'Use AI as a multiplier—not a substitute for judgment.', 'Validate before claiming.', 'Prefer working systems over impressive promises.', 'Keep learning by building.']

export const Route = createFileRoute('/')({
  head: () => ({ meta: [
    { title: 'Dilshodbek Qosimov — Product-minded developer' },
    { name: 'description', content: 'An aspiring product-focused developer from Uzbekistan exploring application architecture, AI-assisted engineering, and thoughtful digital products.' },
  ] }),
  component: Portfolio,
})

function Portfolio() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)
  return (
    <main className="overflow-hidden bg-background text-foreground">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border/70 bg-background/85 backdrop-blur-xl">
        <div className="mx-auto flex h-[72px] max-w-[1440px] items-center justify-between px-5 sm:px-8 lg:px-14">
          <a href="#home" onClick={closeMenu} className="font-mono text-xs font-semibold tracking-[.2em]">DILSHODBEK<span className="text-primary">.</span></a>
          <nav className={`${menuOpen ? 'absolute left-0 right-0 top-[71px] flex flex-col border-b border-border bg-background px-6 py-5' : 'hidden'} gap-5 text-sm text-muted-foreground md:static md:flex md:flex-row md:items-center md:border-0 md:bg-transparent md:p-0`} aria-label="Main navigation">
            {[['About', '#about'], ['Projects', '#projects'], ['Expertise', '#expertise'], ['Journey', '#journey'], ['Contact', '#contact']].map(([label, href]) => <a key={label} href={href} onClick={closeMenu} className="transition-colors hover:text-foreground">{label}</a>)}
          </nav>
          <div className="hidden items-center gap-5 md:flex">
            <a className="text-sm text-muted-foreground transition-colors hover:text-foreground" href="/Dilshodbek-Qosimov-CV.pdf" download>Resume <ArrowDown size={13} className="ml-1 inline" /></a>
            <a className="rounded-full border border-border px-4 py-2 text-xs transition hover:border-primary/60 hover:bg-primary/10" href="#contact">Let’s collaborate <ArrowUpRight size={13} className="ml-1 inline" /></a>
          </div>
          <button className="rounded-md p-2 text-foreground md:hidden" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </header>

      <section id="home" className="relative mx-auto grid min-h-[790px] max-w-[1440px] items-center gap-10 px-5 pb-20 pt-32 sm:px-8 lg:min-h-[900px] lg:grid-cols-[1.1fr_.9fr] lg:px-14 lg:pb-28 lg:pt-28">
        <div className="pointer-events-none absolute -left-40 top-36 h-[500px] w-[500px] rounded-full bg-primary/10 blur-[150px]" />
        <div className="relative z-10 max-w-[760px]">
          <div className="mb-9 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[.22em] text-muted-foreground"><span className="h-px w-8 bg-primary" /> Uzbekistan <span className="text-border">/</span> Product-minded developer</div>
          <h1 className="font-serif text-[clamp(3.5rem,8vw,7.4rem)] leading-[.96] tracking-[-.055em]">Building ideas<br />into <span className="italic text-primary">intelligent</span><br />digital products<span className="text-primary">.</span></h1>
          <p className="mt-8 max-w-[510px] text-base leading-7 text-muted-foreground sm:text-lg">I’m Dilshodbek—a product-focused developer exploring application architecture, AI-assisted engineering, and the systems behind meaningful digital experiences.</p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <a className="group inline-flex items-center gap-3 rounded-full bg-primary px-6 py-3.5 text-sm font-medium text-primary-foreground transition hover:-translate-y-0.5 hover:shadow-lg" href="#projects">Explore projects <ArrowDownRight size={16} className="transition-transform group-hover:translate-x-1 group-hover:translate-y-1" /></a>
            <a className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3.5 text-sm transition hover:border-muted-foreground" href="#contact">Get in touch <MoveUpRight size={14} /></a>
          </div>
          <a href={profile} target="_blank" rel="noreferrer" className="mt-8 inline-flex items-center gap-2 font-mono text-xs text-muted-foreground transition hover:text-foreground"><Github size={15} /> @shakha1210-pixel <ArrowUpRight size={12} /></a>
        </div>
        <HeroArtifact />
        <a href="#about" aria-label="Scroll to about" className="absolute bottom-9 left-5 flex items-center gap-3 font-mono text-[9px] uppercase tracking-[.2em] text-muted-foreground sm:left-8 lg:left-14"><span className="h-px w-8 bg-border" /> Scroll to explore <ArrowDown size={12} /></a>
        <span className="absolute bottom-9 right-5 font-mono text-[9px] tracking-widest text-muted-foreground sm:right-8 lg:right-14">01 — 05</span>
      </section>

      <section id="about" className="border-y border-border/70 bg-card/40">
        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[.62fr_1.38fr] lg:gap-24 lg:px-14 lg:py-32">
          <SectionLabel number="01" label="The person behind the code" />
          <div>
            <h2 className="max-w-4xl font-serif text-4xl leading-[1.12] tracking-tight sm:text-5xl lg:text-6xl">I think in <span className="italic text-primary">systems</span>—and build by learning.</h2>
            <div className="mt-9 grid gap-6 text-sm leading-7 text-muted-foreground sm:grid-cols-2 sm:gap-10">
              <p>I’m an aspiring product-focused developer from Uzbekistan. I’m drawn to how products are shaped: how modules communicate, how data moves, where failure can happen, and whether the whole experience makes sense to the person using it.</p>
              <p>My personal projects use substantial AI assistance. I focus on planning, technical orchestration, review, and product-level validation. The technologies shown describe each project’s environment—not a claim of independent mastery in every tool.</p>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 border-t border-border pt-6 font-mono text-[10px] uppercase tracking-[.13em] text-muted-foreground"><span>Uzbek · Native</span><span>English · B1, progressing toward B2</span><span>UTC +5</span></div>
          </div>
        </div>
      </section>

      <section id="projects" className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 lg:px-14 lg:py-32">
        <div className="mb-14 flex flex-wrap items-end justify-between gap-6"><div><SectionLabel number="02" label="Selected work" /><h2 className="mt-5 font-serif text-4xl tracking-tight sm:text-5xl">Ideas, made <span className="italic text-primary">tangible.</span></h2></div><p className="max-w-sm text-sm leading-6 text-muted-foreground">Independent experiments. Each case study separates what’s implemented from what’s still being explored.</p></div>
        <div className="space-y-7">{projects.map(project => <ProjectCard key={project.number} project={project} />)}</div>
      </section>

      <section id="expertise" className="border-y border-border/70 bg-card/40">
        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[.62fr_1.38fr] lg:gap-24 lg:px-14 lg:py-32">
          <div><SectionLabel number="03" label="Areas of focus" /><h2 className="mt-5 font-serif text-4xl tracking-tight sm:text-5xl">Curiosity, with <span className="italic text-primary">structure.</span></h2><p className="mt-5 max-w-sm text-sm leading-6 text-muted-foreground">A practical view of what I’m exploring and contributing to—without skill percentages or inflated claims.</p></div>
          <div className="divide-y divide-border">{capabilities.map(([n, title, text]) => <div key={n} className="group grid gap-3 py-5 transition-colors hover:border-primary/40 sm:grid-cols-[44px_1fr_1.2fr] sm:items-baseline"><span className="font-mono text-[10px] text-primary">{n}</span><h3 className="text-base font-medium">{title}</h3><p className="text-sm leading-6 text-muted-foreground">{text}</p></div>)}</div>
        </div>
      </section>

      <section className="relative mx-auto max-w-[1440px] px-5 py-24 sm:px-8 lg:px-14 lg:py-32">
        <div className="grid gap-12 lg:grid-cols-[.62fr_1.38fr] lg:gap-24"><div><SectionLabel number="04" label="Engineering philosophy" /><p className="mt-6 font-mono text-[10px] uppercase tracking-[.2em] text-muted-foreground">A way of working</p></div>
          <div className="divide-y divide-border">{principles.map((text, i) => <div key={text} className="flex items-center gap-5 py-5 sm:py-6"><span className="font-mono text-[10px] text-primary">0{i + 1}</span><p className="font-serif text-2xl tracking-tight sm:text-3xl">{text}</p></div>)}</div></div>
      </section>

      <section id="journey" className="border-y border-border/70 bg-card/40">
        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[.62fr_1.38fr] lg:gap-24 lg:px-14 lg:py-32">
          <div><SectionLabel number="05" label="Journey so far" /><h2 className="mt-5 font-serif text-4xl tracking-tight sm:text-5xl">Learning by <span className="italic text-primary">making.</span></h2></div>
          <div className="relative border-l border-border pl-7">
            <div className="absolute -left-[5px] top-2 h-[9px] w-[9px] rounded-full bg-primary shadow-[0_0_16px_oklch(0.72_0.17_286_/_0.7)]" />
            <span className="font-mono text-[10px] uppercase tracking-[.2em] text-primary">2022</span>
            <h3 className="mt-3 text-xl font-medium">Rakhmonov IT School</h3><p className="mt-1 text-sm text-muted-foreground">Frontend Development · Samarkand</p>
            <div className="mt-8 grid gap-6 border-t border-border pt-6 sm:grid-cols-2"><div><p className="font-mono text-[10px] uppercase tracking-[.16em] text-muted-foreground">Certificates</p><p className="mt-3 text-sm">Frontend Development<br />HTML / CSS</p></div><div><p className="font-mono text-[10px] uppercase tracking-[.16em] text-muted-foreground">Achievements</p><p className="mt-3 text-sm leading-6 text-muted-foreground">Repeated first-place results in district-level IT competitions; participated at regional level.</p></div></div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 lg:px-14 lg:py-32">
        <div className="grid gap-10 border-b border-border pb-10 sm:grid-cols-[1fr_auto] sm:items-end"><div><SectionLabel number="06" label="Good work starts with a conversation" /><h2 className="mt-6 max-w-3xl font-serif text-4xl leading-tight sm:text-6xl">Small, thoughtful steps.<br /><span className="italic text-primary">Meaningful products.</span></h2></div><p className="max-w-sm text-sm leading-6 text-muted-foreground">Open to exploring frontend websites, landing pages, AI-assisted product prototypes, and early-stage technical collaboration.</p></div>
        <div className="grid gap-10 py-10 sm:grid-cols-[1fr_auto] sm:items-center"><div><p className="text-sm text-muted-foreground">Interested in building something together?</p><a className="mt-2 inline-flex items-center gap-2 text-xl transition hover:text-primary sm:text-2xl" href="mailto:shakha1210@gmail.com">shakha1210@gmail.com <ArrowUpRight size={18} /></a></div><div className="flex flex-wrap gap-3"><a href={profile} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-3 text-sm transition hover:border-primary/60"><Github size={15} /> GitHub <ArrowUpRight size={13} /></a><a href="/Dilshodbek-Qosimov-CV.pdf" download className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-3 text-sm transition hover:border-primary/60">Download CV <ArrowDown size={13} /></a></div></div>
        <div id="contact" className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-primary/20 bg-primary/[.045] p-5 sm:p-7"><div className="flex items-start gap-4"><span className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary"><Mail size={16} /></span><div><p className="text-sm font-medium">A direct line, no pretend form.</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Email opens in your mail app. A résumé PDF can be added when a verified file is available.</p></div></div><a href="mailto:shakha1210@gmail.com?subject=Let%27s%20collaborate" className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition hover:-translate-y-0.5">Say hello <ArrowUpRight size={15} /></a></div>
      </section>

      <footer className="border-t border-border"><div className="mx-auto flex max-w-[1440px] flex-col gap-4 px-5 py-7 font-mono text-[9px] uppercase tracking-[.15em] text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-14"><a href="#home" className="font-semibold tracking-[.2em] text-foreground">DILSHODBEK<span className="text-primary">.</span></a><span>Built with intention · Documented with transparency · Always iterating</span><a href={profile} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 hover:text-foreground">GitHub <ArrowUpRight size={12} /></a></div></footer>
    </main>
  )
}

function HeroArtifact() {
  return <div aria-label="Abstract systems map representing ideas becoming software" className="relative mx-auto aspect-square w-full max-w-[510px] lg:ml-auto">
    <div className="absolute inset-[7%] rounded-full border border-border/70" /><div className="absolute inset-[18%] rounded-full border border-border/60" /><div className="absolute inset-[30%] rounded-full border border-primary/20" />
    <div className="absolute inset-[8%] rounded-full bg-[radial-gradient(circle_at_48%_48%,oklch(0.48_0.17_286_/_0.18),transparent_60%)]" />
    <div className="absolute left-1/2 top-1/2 grid h-36 w-36 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-[2rem] border border-primary/30 bg-card/80 shadow-[0_0_85px_oklch(0.52_0.15_286_/_0.13)] backdrop-blur"><div className="text-center"><Braces className="mx-auto text-primary" size={32} strokeWidth={1.2} /><span className="mt-3 block font-mono text-[9px] uppercase tracking-[.18em] text-muted-foreground">product / systems</span></div></div>
    <div className="absolute left-[12%] top-[25%] rounded-xl border border-border bg-card/90 px-3 py-2 shadow-md"><span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-primary" /> architecture</span></div>
    <div className="absolute right-[1%] top-[43%] rounded-xl border border-border bg-card/90 px-3 py-2 shadow-md"><span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-accent" /> experiments</span></div>
    <div className="absolute bottom-[17%] left-[21%] rounded-xl border border-border bg-card/90 px-3 py-2 shadow-md"><span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-primary/70" /> thoughtful AI</span></div>
    <span className="absolute right-[22%] top-[15%] h-2 w-2 rounded-full bg-accent shadow-[0_0_18px_oklch(0.76_0.11_226)]" /><span className="absolute bottom-[27%] right-[17%] h-1.5 w-1.5 rounded-full bg-primary" />
    <span className="absolute left-[4%] bottom-[35%] font-mono text-[9px] tracking-widest text-muted-foreground">IDEA → SYSTEM → PRODUCT</span>
  </div>
}

function SectionLabel({ number, label }: { number: string; label: string }) {
  return <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[.17em] text-muted-foreground"><span className="text-primary">{number}</span><span className="h-px w-7 bg-border" />{label}</div>
}

function ProjectCard({ project }: { project: (typeof projects)[number] }) {
  return <article className={`group overflow-hidden rounded-[1.4rem] border border-border bg-card transition duration-300 hover:-translate-y-1 hover:border-primary/30 hover:shadow-lg project-${project.color}`}>
    <div className="grid lg:grid-cols-[1.02fr_.98fr]">
      <div className="relative flex min-h-[300px] items-center justify-center overflow-hidden border-b border-border bg-background p-7 lg:min-h-[390px] lg:border-b-0 lg:border-r sm:p-10">
        <div className="absolute inset-0 opacity-75 [background-image:linear-gradient(to_right,oklch(0.29_0.018_268_/_0.22)_1px,transparent_1px),linear-gradient(to_bottom,oklch(0.29_0.018_268_/_0.22)_1px,transparent_1px)] [background-size:32px_32px]" />
        <div className="absolute -left-20 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-[90px]" />
        <div className="relative w-full max-w-[400px] overflow-hidden rounded-xl border border-border bg-card/95 shadow-lg transition duration-500 group-hover:scale-[1.025]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3"><div className="flex gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40"/><i className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40"/><i className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40"/></div><span className="font-mono text-[8px] uppercase tracking-[.15em] text-muted-foreground">{project.title} / workspace</span><Sparkles size={12} className="text-primary" /></div>
          <div className="grid min-h-[198px] grid-cols-[82px_1fr] sm:min-h-[220px]">
            <aside className="border-r border-border p-3"><div className="mb-4 h-2 w-10 rounded bg-primary/50"/><div className="space-y-3">{['Overview', 'Models', 'Agents', 'Workspace'].map((item, i) => <div key={item} className={`flex items-center gap-1.5 font-mono text-[7px] ${i === 1 ? 'text-foreground' : 'text-muted-foreground'}`}><Circle size={6} className={i === 1 ? 'fill-primary text-primary' : ''}/>{item}</div>)}</div></aside>
            <div className="p-4 sm:p-5"><span className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{project.status}</span><p className="mt-3 font-serif text-xl">{project.title} <span className="text-primary">workspace</span></p><div className="mt-4 grid grid-cols-2 gap-2">{project.details.slice(0, 4).map((detail, i) => <div key={detail} className="rounded-md border border-border/80 p-2"><span className="block h-1 w-5 rounded bg-primary/60"/><span className="mt-2 block text-[8px] leading-3 text-muted-foreground">{detail}</span><span className={`mt-2 block h-1 rounded ${i % 2 ? 'w-1/2 bg-accent/40' : 'w-2/3 bg-primary/30'}`}/></div>)}</div></div>
          </div>
        </div>
        <span className="absolute bottom-4 left-5 font-mono text-[8px] uppercase tracking-[.15em] text-muted-foreground/75">Conceptual UI composition · not a product screenshot</span>
      </div>
      <div className="flex flex-col justify-between p-6 sm:p-9 lg:p-11">
        <div><div className="flex items-center justify-between"><span className="font-mono text-[10px] uppercase tracking-[.18em] text-primary">Project {project.number} <span className="mx-1 text-border">/</span> {project.subtitle}</span><span className="rounded-full border border-border px-2.5 py-1 font-mono text-[8px] text-muted-foreground">{project.status}</span></div>
          <h3 className="mt-5 font-serif text-4xl tracking-tight sm:text-5xl">{project.title}<span className="text-primary">.</span></h3><p className="mt-4 max-w-lg text-sm leading-6 text-muted-foreground">{project.description}</p>
          <div className="mt-7 grid gap-2 sm:grid-cols-2">{project.details.map(detail => <div key={detail} className="flex items-start gap-2 text-xs leading-5 text-foreground/80"><Check size={13} className="mt-1 shrink-0 text-primary" />{detail}</div>)}</div>
        </div>
        <div className="mt-8 border-t border-border pt-5"><p className="font-mono text-[9px] leading-5 tracking-wide text-muted-foreground">{project.stack}</p><a href={project.href} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-2 text-sm transition hover:text-primary">Explore repository <ArrowUpRight size={14} className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></a></div>
      </div>
    </div>
  </article>
}
