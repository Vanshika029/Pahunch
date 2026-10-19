import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDownUp, ArrowLeft, ArrowRight, BadgeCheck, Banknote, Bell, BookOpenCheck,
  Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, Clock3, FileCheck2,
  FileText, Filter, HeartHandshake, Home, Landmark, LayoutDashboard, LogOut, Menu,
  MessageCircle, Search, Send, ShieldCheck, Sparkles, UserRound, X,
} from 'lucide-react'

const API = `${(import.meta.env.VITE_API_URL || '').replace(/\/$/, '')}/api/v1`
const categories = ['All schemes', 'Agriculture', 'Education', 'Healthcare', 'Housing', 'Business']
const statusLabels = {
  submitted: 'Application received',
  under_review: 'Under review',
  documents_required: 'Action needed',
  approved: 'Approved',
  rejected: 'Not approved',
  withdrawn: 'Withdrawn',
}

async function request(path, options = {}, token) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload.detail
    const message = typeof detail === 'string' ? detail : detail?.message || JSON.stringify(detail) || 'Something went wrong'
    throw new Error(message)
  }
  return payload
}

function IconMark({ small = false }) {
  return <div className={`brand-mark${small ? ' brand-mark-small' : ''}`} aria-hidden="true"><HeartHandshake /></div>
}

function Login({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('demo@pahunch.in')
  const [password, setPassword] = useState('Pahunch123!')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const path = mode === 'login' ? '/auth/login' : '/auth/register'
      const body = mode === 'login' ? { email, password } : { email, password, full_name: name }
      const result = await request(path, { method: 'POST', body: JSON.stringify(body) })
      onLogin(result.access_token, result.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-art">
        <div className="auth-brand"><IconMark /><span>pahunch</span></div>
        <div className="auth-art-copy">
          <span className="eyebrow light-eyebrow"><span /> YOUR NEXT STEP, MADE SIMPLE</span>
          <h1>Support should be easy to find.</h1>
          <p>Discover government schemes, understand what you need, and keep every application on track.</p>
        </div>
        <div className="auth-art-footer"><ShieldCheck size={18} /> Clear information. Your details stay yours.</div>
        <div className="auth-orbit orbit-one" /><div className="auth-orbit orbit-two" />
      </section>
      <section className="auth-form-side">
        <div className="auth-form-wrap">
          <span className="eyebrow">WELCOME TO PAHUNCH</span>
          <h2>{mode === 'login' ? 'Good to have you here.' : 'Create your account.'}</h2>
          <p className="muted">{mode === 'login' ? 'Sign in to see the support available to you.' : 'A few details to get your scheme journey started.'}</p>
          {mode === 'login' && <div className="demo-note"><Sparkles size={16} /><span><strong>Explore the demo</strong><br />demo@pahunch.in <span className="demo-divider">/</span> Pahunch123!</span></div>}
          <form className="auth-fields" onSubmit={submit}>
            {mode === 'register' && <label>Full name<input required minLength="2" autoComplete="name" value={name} onChange={event => setName(event.target.value)} placeholder="Your name" /></label>}
            <label>Email address<input required type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" /></label>
            <label>Password<input required minLength={mode === 'register' ? 10 : 1} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={event => setPassword(event.target.value)} placeholder={mode === 'register' ? 'At least 10 characters' : 'Your password'} /></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary button-wide" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}<ArrowRight size={17} /></button>
          </form>
          <p className="auth-switch">{mode === 'login' ? 'New to Pahunch?' : 'Already have an account?'} <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></p>
          <p className="auth-legal">By continuing, you agree to use scheme information as guidance and verify final requirements with the official department.</p>
        </div>
      </section>
    </main>
  )
}

function SchemeCard({ scheme, onOpen, compact = false }) {
  const categoryIcon = { Agriculture: '🌾', Education: '📚', Healthcare: '✚', Housing: '⌂', Business: '↗' }
  return (
    <article className={`scheme-card${compact ? ' scheme-card-compact' : ''}`}>
      <div className="scheme-card-top">
        <div className={`scheme-symbol scheme-symbol-${scheme.category?.toLowerCase()}`} aria-hidden="true">{categoryIcon[scheme.category] || '✦'}</div>
        {scheme.eligible ? <span className="eligibility-tag"><CheckCircle2 size={13} /> Likely eligible</span> : <span className="not-eligible-tag">Check criteria</span>}
      </div>
      <span className="scheme-category">{scheme.category} <span>·</span> {scheme.department}</span>
      <h3>{scheme.name}</h3>
      <p className="scheme-summary">{scheme.summary}</p>
      <div className="scheme-benefit"><Banknote size={16} /><span>{scheme.benefit}</span></div>
      <div className="scheme-card-bottom">
        <span className="doc-count"><FileText size={14} /> {scheme.documents.length} documents</span>
        <button className="text-button" onClick={() => onOpen(scheme)}>{scheme.applied ? 'View application' : 'View details'} <ArrowRight size={15} /></button>
      </div>
    </article>
  )
}

function SchemeModal({ scheme, onClose, onApply, busy }) {
  if (!scheme) return null
  return (
    <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="scheme-title">
        <button className="icon-button modal-close" onClick={onClose} aria-label="Close"><X size={19} /></button>
        <div className="modal-heading">
          <div className="scheme-symbol scheme-symbol-large"><Landmark /></div>
          <span className="scheme-category">{scheme.category} · {scheme.department}</span>
          <h2 id="scheme-title">{scheme.name}</h2>
          <p>{scheme.summary}</p>
        </div>
        <div className="detail-benefit"><Banknote size={19} /><div><span>WHAT YOU COULD RECEIVE</span><strong>{scheme.benefit}</strong></div></div>
        {scheme.eligibility_reasons?.length > 0 && <div className="notice notice-warm"><CircleHelp size={18} /><div><strong>Check your eligibility</strong><ul>{scheme.eligibility_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div></div>}
        {scheme.eligible && <div className="notice notice-green"><BadgeCheck size={18} /><span><strong>You may be eligible.</strong> Final decisions are made by the scheme authority.</span></div>}
        <div className="detail-documents">
          <h3><FileCheck2 size={17} /> Documents to prepare</h3>
          <ul>{scheme.documents.map(document => <li key={document}><Check size={15} />{document}</li>)}</ul>
        </div>
        <p className="detail-footnote">Requirements can change. Please confirm the latest details with the official government department.</p>
        <div className="modal-actions">
          <button className="button button-outline" onClick={onClose}>Close</button>
          {scheme.applied
            ? <button className="button button-primary" onClick={onClose}>Application submitted <Check size={16} /></button>
            : <button className="button button-primary" disabled={!scheme.eligible || busy} onClick={() => onApply(scheme)}>{busy ? 'Submitting…' : 'Start application'} <ArrowRight size={16} /></button>}
        </div>
      </section>
    </div>
  )
}

function Applications({ applications, onWithdraw }) {
  const [expanded, setExpanded] = useState(null)
  if (!applications.length) return <div className="empty-state"><div className="empty-icon"><FileText /></div><h3>Your applications will show up here</h3><p>When you apply for a scheme, you can follow every update and find your reference number in one place.</p></div>
  return (
    <div className="application-list">
      {applications.map(application => {
        const isOpen = expanded === application.id
        return (
          <article className="application-card" key={application.id}>
            <div className="application-main">
              <div className="scheme-symbol scheme-symbol-small"><Landmark size={19} /></div>
              <div className="application-info"><span className="scheme-category">{application.department}</span><h3>{application.scheme_name}</h3><span className="reference">Reference <strong>{application.reference_number}</strong></span></div>
              <span className={`status-pill status-${application.status}`}><span />{statusLabels[application.status] || application.status}</span>
              <button className="icon-button application-expand" onClick={() => setExpanded(isOpen ? null : application.id)} aria-expanded={isOpen} aria-label={`${isOpen ? 'Hide' : 'Show'} application updates`}><ChevronDown size={19} /></button>
            </div>
            <div className="application-progress" aria-label={`Status: ${statusLabels[application.status]}`}>
              {['submitted', 'under_review', 'approved'].map((step, index) => <span key={step} className={`progress-step${application.status === step ? ' active' : ''}${['approved', 'rejected', 'withdrawn'].includes(application.status) && index < 2 ? ' complete' : ''}`}><i />{index === 0 ? 'Submitted' : index === 1 ? 'In review' : 'Decision'}</span>)}
            </div>
            {isOpen && <div className="application-details">
              <div className="timeline">{application.timeline.map((event, index) => <div className="timeline-item" key={`${event.status}-${index}`}><span className={`timeline-dot${index === application.timeline.length - 1 ? ' timeline-dot-current' : ''}`} /><div><strong>{event.message}</strong><span>{statusLabels[event.status] || event.status} · {new Date(`${event.created_at}Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span></div></div>)}</div>
              <div className="application-detail-footer"><span>Submitted {new Date(`${application.created_at}Z`).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}</span>{!['approved', 'rejected', 'withdrawn'].includes(application.status) && <button className="text-button text-danger" onClick={() => onWithdraw(application)}>Withdraw application</button>}</div>
            </div>}
          </article>
        )
      })}
    </div>
  )
}

function Profile({ profile, onSave, busy }) {
  const [form, setForm] = useState(profile)
  const [saved, setSaved] = useState(false)
  useEffect(() => setForm(profile), [profile])
  function change(key, value) { setForm(current => ({ ...current, [key]: value })) }
  async function submit(event) {
    event.preventDefault()
    const result = await onSave({ ...form, age: form.age === '' ? null : Number(form.age), annual_income: form.annual_income === '' ? null : Number(form.annual_income) })
    if (result) setSaved(true)
  }
  return (
    <div className="profile-layout">
      <section className="profile-card">
        <div className="section-title-row"><div><span className="eyebrow">YOUR DETAILS</span><h2>Eligibility profile</h2><p>These details help us find schemes that may be a fit for you.</p></div><div className="profile-avatar"><UserRound /></div></div>
        <form className="profile-form" onSubmit={submit}>
          <label>Age<input type="number" min="0" max="120" value={form.age ?? ''} onChange={event => change('age', event.target.value)} placeholder="Your age" /></label>
          <label>Annual household income (₹)<input type="number" min="0" value={form.annual_income ?? ''} onChange={event => change('annual_income', event.target.value)} placeholder="e.g. 250000" /></label>
          <label>State / Union Territory<select value={form.state || ''} onChange={event => change('state', event.target.value)}><option value="">Choose your state</option>{['Andhra Pradesh', 'Assam', 'Bihar', 'Delhi', 'Gujarat', 'Haryana', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Odisha', 'Punjab', 'Rajasthan', 'Tamil Nadu', 'Telangana', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal'].map(state => <option key={state}>{state}</option>)}</select></label>
          <label>Social category<select value={form.category || ''} onChange={event => change('category', event.target.value)}><option value="">Choose a category</option>{['General', 'OBC', 'SC', 'ST', 'Other'].map(category => <option key={category}>{category}</option>)}</select></label>
          <label>Gender<select value={form.gender || ''} onChange={event => change('gender', event.target.value)}><option value="">Prefer not to say</option>{['female', 'male', 'other'].map(gender => <option key={gender} value={gender}>{gender[0].toUpperCase() + gender.slice(1)}</option>)}</select></label>
          <div className="profile-save-row"><span><ShieldCheck size={15} /> Your profile is private and used only for matching.</span><button className="button button-primary" disabled={busy}>{busy ? 'Saving…' : saved ? 'Saved' : 'Save details'}{saved ? <Check size={16} /> : <ArrowRight size={16} />}</button></div>
        </form>
      </section>
      <aside className="profile-tip"><div className="tip-icon"><Sparkles size={20} /></div><h3>A little more about you goes a long way.</h3><p>Complete your profile to get more relevant scheme matches. Your eligibility results are a helpful starting point, not an official decision.</p><div className="tip-rule" /><div className="tip-meta"><ShieldCheck size={16} /> Your information stays in your account</div></aside>
    </div>
  )
}

function Assistant({ token, onClose }) {
  const [messages, setMessages] = useState([{ role: 'assistant', text: 'Namaste! I can help you explore schemes, understand document lists, or check what might fit your profile. What would you like to know?' }])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const prompts = ['Which schemes might I be eligible for?', 'What documents should I prepare?', 'How do I track my application?']
  async function send(text = input) {
    const message = text.trim()
    if (!message || busy) return
    setInput('')
    setError('')
    setMessages(current => [...current, { role: 'user', text: message }])
    setBusy(true)
    try {
      const answer = await request('/assistant/chat', { method: 'POST', body: JSON.stringify({ message }) }, token)
      setMessages(current => [...current, { role: 'assistant', text: answer.reply }])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <aside className="assistant-panel" aria-label="Pahunch assistant">
      <header className="assistant-head"><div className="assistant-avatar"><Sparkles size={19} /></div><div><strong>Your Pahunch guide</strong><span><i /> Here to help</span></div><button className="icon-button" onClick={onClose} aria-label="Close assistant"><X size={19} /></button></header>
      <div className="assistant-note"><Sparkles size={14} /> Helpful guidance, based on your profile</div>
      <div className="assistant-messages" aria-live="polite">
        {messages.map((message, index) => <div className={`chat-message ${message.role}`} key={index}><div>{message.text}</div></div>)}
        {busy && <div className="chat-message assistant"><div className="typing-dots"><i /><i /><i /></div></div>}
      </div>
      {messages.length < 3 && <div className="suggested-prompts">{prompts.map(prompt => <button key={prompt} onClick={() => send(prompt)}>{prompt}<ArrowRight size={13} /></button>)}</div>}
      {error && <p className="assistant-error" role="alert">{error}</p>}
      <form className="chat-input" onSubmit={event => { event.preventDefault(); send() }}><input value={input} onChange={event => setInput(event.target.value)} placeholder="Ask me anything…" aria-label="Message the assistant" /><button aria-label="Send message" disabled={!input.trim() || busy}><Send size={17} /></button></form>
      <p className="assistant-disclaimer">Demo assistant · verify official scheme information before applying.</p>
    </aside>
  )
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('pahunch_token'))
  const [user, setUser] = useState(null)
  const [page, setPage] = useState('overview')
  const [profile, setProfile] = useState({ age: '', annual_income: '', state: '', category: '', gender: '' })
  const [schemes, setSchemes] = useState([])
  const [applications, setApplications] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All schemes')
  const [sort, setSort] = useState('featured')
  const [activeScheme, setActiveScheme] = useState(null)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const refresh = useCallback(async (authToken = token) => {
    if (!authToken) return
    setLoading(true)
    setError('')
    try {
      const [me, catalogue, tracked] = await Promise.all([
        request('/auth/me', {}, authToken),
        request('/schemes?page=1&page_size=50&sort=featured', {}, authToken),
        request('/applications', {}, authToken),
      ])
      setUser(me)
      setProfile(me.profile)
      setSchemes(catalogue.items)
      setApplications(tracked.items)
    } catch (err) {
      if (err.message.includes('token') || err.message.includes('Sign in')) {
        localStorage.removeItem('pahunch_token')
        setToken(null)
      }
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { if (token) refresh(token) }, [token, refresh])

  const visibleSchemes = useMemo(() => {
    return schemes
      .filter(scheme => category === 'All schemes' || scheme.category === category)
      .filter(scheme => `${scheme.name} ${scheme.summary} ${scheme.department}`.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'deadline' ? (a.deadline || '9999').localeCompare(b.deadline || '9999') : Number(b.featured) - Number(a.featured))
  }, [schemes, category, query, sort])

  function signedIn(accessToken, account) {
    localStorage.setItem('pahunch_token', accessToken)
    setUser(account)
    setToken(accessToken)
    setError('')
  }

  function signOut() {
    localStorage.removeItem('pahunch_token')
    setToken(null); setUser(null); setSchemes([]); setApplications([])
  }

  async function applyToScheme(scheme) {
    setBusy(true)
    setError('')
    try {
      await request('/applications', { method: 'POST', body: JSON.stringify({ scheme_id: scheme.id }) }, token)
      setActiveScheme(null)
      setNotice('Your application has been submitted. Keep the reference number safe.')
      await refresh()
      setPage('applications')
    } catch (err) {
      setError(err.message)
      setActiveScheme(null)
    } finally {
      setBusy(false)
    }
  }

  async function withdraw(application) {
    if (!window.confirm(`Withdraw your application for ${application.scheme_name}?`)) return
    try {
      await request(`/applications/${application.id}`, { method: 'PATCH' }, token)
      setNotice('Your application has been withdrawn.')
      await refresh()
    } catch (err) { setError(err.message) }
  }

  async function saveProfile(updated) {
    setBusy(true)
    setError('')
    try {
      const saved = await request('/profile', { method: 'PUT', body: JSON.stringify(updated) }, token)
      setProfile(saved)
      setNotice('Your profile has been updated.')
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally { setBusy(false) }
  }

  if (!token) return <Login onLogin={signedIn} />

  const eligibleCount = schemes.filter(scheme => scheme.eligible).length
  const inProgressCount = applications.filter(application => ['submitted', 'under_review', 'documents_required'].includes(application.status)).length
  const pageTitle = { overview: 'Good morning', schemes: 'Find your schemes', applications: 'My applications', profile: 'Your profile' }[page]
  const navItems = [
    { id: 'overview', label: 'Overview', Icon: LayoutDashboard },
    { id: 'schemes', label: 'Explore schemes', Icon: Landmark, count: schemes.length },
    { id: 'applications', label: 'My applications', Icon: FileCheck2, count: applications.length },
    { id: 'profile', label: 'Eligibility profile', Icon: UserRound },
  ]

  return (
    <div className="app-shell">
      <aside className={`sidebar${mobileNavOpen ? ' sidebar-open' : ''}`}>
        <button className="sidebar-brand" onClick={() => { setPage('overview'); setMobileNavOpen(false) }}><IconMark /><span>pahunch<small>BENEFITS, WITHIN REACH</small></span></button>
        <span className="sidebar-label">YOUR SPACE</span>
        <nav className="main-nav" aria-label="Main navigation">{navItems.map(({ id, label, Icon, count }) => <button key={id} className={`nav-link${page === id ? ' nav-active' : ''}`} onClick={() => { setPage(id); setMobileNavOpen(false) }}><Icon size={18} /><span>{label}</span>{count > 0 && <small>{count}</small>}</button>)}</nav>
        <div className="sidebar-bottom">
          <div className="help-card"><div className="help-card-icon"><BookOpenCheck size={18} /></div><strong>Need a hand?</strong><p>Your guide can explain schemes and help you get started.</p><button onClick={() => setAssistantOpen(true)}>Ask Pahunch <ArrowRight size={14} /></button></div>
          <button className="user-menu" onClick={() => setPage('profile')}><div className="user-avatar">{user?.full_name?.split(' ').map(part => part[0]).slice(0, 2).join('').toUpperCase() || 'U'}</div><span><strong>{user?.full_name || 'Your account'}</strong><small>Citizen account</small></span><ChevronDown size={16} /></button>
        </div>
      </aside>
      {mobileNavOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <main className="main-area">
        <header className="topbar"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)}><Menu size={21} /></button><div className="breadcrumbs">Pahunch <ChevronRight size={14} /> <span>{page === 'overview' ? 'Your space' : navItems.find(item => item.id === page)?.label}</span></div><div className="topbar-actions"><button className="assistant-top-button" onClick={() => setAssistantOpen(true)}><Sparkles size={16} /> <span>Ask your guide</span></button><span className="topbar-divider" /><button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button><button className="topbar-avatar" onClick={() => setPage('profile')} aria-label="Open your profile">{user?.full_name?.[0]?.toUpperCase() || 'U'}</button></div></header>
        <div className="page-content">
          <div className="page-heading"><div><span className="eyebrow"><span className="live-dot" /> YOUR PAHUNCH DASHBOARD</span><h1>{page === 'overview' ? <>Good morning, {user?.full_name?.split(' ')[0] || 'there'} <span className="heading-sun">✳</span></> : pageTitle}</h1><p>{page === 'overview' ? 'Let’s find the support that can make a difference for you.' : page === 'schemes' ? 'Explore support from government programmes across India.' : page === 'applications' ? 'Every application, update, and reference number in one place.' : 'Keep your details up to date for more relevant matches.'}</p></div><div className="heading-date"><span>TODAY</span><strong>{new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date())}</strong></div></div>
          {error && <div className="alert alert-error" role="alert"><CircleHelp size={17} /><span>{error}</span><button onClick={() => { setError(''); refresh() }} aria-label="Dismiss error"><X size={16} /></button></div>}
          {notice && <div className="alert alert-success" role="status"><CheckCircle2 size={17} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss notification"><X size={16} /></button></div>}
          {loading ? <div className="loading-state"><span className="spinner" /> Loading your Pahunch…</div> : <>
            {page === 'overview' && <Overview schemes={schemes} applications={applications} eligibleCount={eligibleCount} inProgressCount={inProgressCount} onPage={setPage} onOpen={setActiveScheme} profile={profile} />}
            {page === 'schemes' && <section className="directory-section"><div className="directory-toolbar"><label className="search-box"><Search size={18} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search schemes, benefits, departments…" aria-label="Search schemes" />{query && <button onClick={() => setQuery('')} aria-label="Clear search"><X size={15} /></button>}</label><label className="sort-select"><ArrowDownUp size={16} /><select value={sort} onChange={event => setSort(event.target.value)} aria-label="Sort schemes"><option value="featured">Featured</option><option value="name">Name A–Z</option><option value="deadline">Closing soon</option></select><ChevronDown size={14} /></label></div><div className="category-tabs" aria-label="Filter by category">{categories.map(item => <button key={item} className={category === item ? 'category-tab active' : 'category-tab'} onClick={() => setCategory(item)}>{item}</button>)}</div><div className="results-meta"><span><strong>{visibleSchemes.length}</strong> schemes to explore</span><span><CheckCircle2 size={14} /> Eligibility matched to your profile</span></div>{visibleSchemes.length ? <div className="scheme-grid">{visibleSchemes.map(scheme => <SchemeCard key={scheme.id} scheme={scheme} onOpen={setActiveScheme} />)}</div> : <div className="empty-state"><Search size={28} /><h3>No schemes found</h3><p>Try a different keyword or category.</p><button className="text-button" onClick={() => { setQuery(''); setCategory('All schemes') }}>Clear filters <ArrowRight size={15} /></button></div>}</section>}
            {page === 'applications' && <section className="tracker-section"><div className="tracker-intro"><div className="tracker-intro-icon"><Clock3 /></div><div><h2>Application tracker</h2><p>Application updates appear here as they’re recorded. For an official update, contact the department using your reference number.</p></div><div className="tracker-total"><strong>{applications.length}</strong><span>total applications</span></div></div><Applications applications={applications} onWithdraw={withdraw} /></section>}
            {page === 'profile' && <Profile profile={profile} onSave={saveProfile} busy={busy} />}
          </>}
          <footer className="page-footer"><span>© 2026 Pahunch <span>·</span> Made to make support easier to reach.</span><button onClick={() => setAssistantOpen(true)}><CircleHelp size={14} /> Help & guidance</button><button className="footer-signout" onClick={signOut}><LogOut size={14} /> Sign out</button></footer>
        </div>
      </main>
      {assistantOpen && <Assistant token={token} onClose={() => setAssistantOpen(false)} />}
      <SchemeModal scheme={activeScheme} onClose={() => setActiveScheme(null)} onApply={applyToScheme} busy={busy} />
    </div>
  )
}

function Overview({ schemes, applications, eligibleCount, inProgressCount, onPage, onOpen, profile }) {
  const featured = schemes.filter(scheme => scheme.featured).slice(0, 3)
  const profileComplete = [profile.age, profile.annual_income, profile.state].every(value => value !== null && value !== '')
  return (
    <div className="overview-content">
      <section className="welcome-banner">
        <div className="banner-copy"><span className="banner-kicker"><Sparkles size={14} /> YOUR NEXT STEP STARTS HERE</span><h2>Support that meets<br />you where you are.</h2><p>Discover benefits, understand what you need, and take your next step with confidence.</p><button className="banner-button" onClick={() => onPage('schemes')}>Explore your matches <ArrowRight size={16} /></button></div>
        <div className="banner-art" aria-hidden="true"><div className="art-sun" /><div className="art-circle art-circle-one" /><div className="art-circle art-circle-two" /><div className="art-leaf leaf-one" /><div className="art-leaf leaf-two" /><div className="art-card"><HeartHandshake size={27} /><span>A little support<br />goes a long way.</span></div><div className="art-stem" /></div>
        <div className="banner-index">01 <span>/</span> 03</div>
      </section>
      <section className="stats-row" aria-label="Your scheme summary"><button className="stat-card stat-highlight" onClick={() => onPage('schemes')}><span className="stat-icon"><BadgeCheck size={18} /></span><span className="stat-label">POTENTIAL MATCHES</span><strong>{eligibleCount}<small> schemes</small></strong><span className="stat-foot">Based on your profile <ArrowRight size={14} /></span></button><button className="stat-card" onClick={() => onPage('applications')}><span className="stat-icon stat-icon-amber"><FileCheck2 size={18} /></span><span className="stat-label">IN PROGRESS</span><strong>{inProgressCount}<small> applications</small></strong><span className="stat-foot">{applications.length ? 'See your latest updates' : 'Your applications appear here'} <ArrowRight size={14} /></span></button><button className="stat-card" onClick={() => onPage('profile')}><span className="stat-icon stat-icon-blue"><UserRound size={18} /></span><span className="stat-label">PROFILE STATUS</span><strong className="stat-word">{profileComplete ? 'Looking good' : 'Almost there'}</strong><span className="stat-foot">{profileComplete ? 'Keep details up to date' : 'Add details for better matches'} <ArrowRight size={14} /></span></button></section>
      {!profileComplete && <button className="profile-nudge" onClick={() => onPage('profile')}><span><Sparkles size={17} /><strong>Get more relevant matches</strong><span>Complete your eligibility profile to see schemes that may be right for you.</span></span><ArrowRight size={18} /></button>}
      <section className="featured-section"><div className="section-heading"><div><span className="eyebrow">A GOOD PLACE TO START</span><h2>Popular schemes</h2><p>Explore programmes people are looking into.</p></div><button className="view-all-button" onClick={() => onPage('schemes')}>View all schemes <ArrowRight size={15} /></button></div>{featured.length ? <div className="scheme-grid">{featured.map(scheme => <SchemeCard key={scheme.id} scheme={scheme} onOpen={onOpen} compact />)}</div> : <div className="loading-state"><span className="spinner" />Loading schemes…</div>}</section>
      <section className="bottom-guidance"><div className="guidance-mark"><ShieldCheck size={20} /></div><div><strong>Not sure where to begin?</strong><p>Ask your guide about eligibility, documents, or application updates.</p></div><button onClick={() => document.querySelector('.assistant-top-button')?.click()}>Talk to your guide <MessageCircle size={15} /></button></section>
    </div>
  )
}

export default App
