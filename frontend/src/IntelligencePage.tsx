import { useState } from 'react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity,
  Bot,
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';

const DEMO_ORGANIZATION_ID = '11111111-1111-4111-8111-111111111111';

type Finding = {
  id: string;
  title: string;
  detail: string;
  severity: 'info' | 'watch' | 'critical';
  evidence: string;
};

type DataAnalystReport = {
  status: string;
  agent: string;
  period: { start_date: string; end_date: string };
  currency: string;
  summary: string;
  metrics: Record<string, number | null>;
  findings: Finding[];
  data_sources: string[];
  inventory_snapshot_dates: string[];
};

type BusinessAnalystReport = {
  status: string;
  agent: string;
  answer: string;
  provider?: string;
  model?: string;
  tools_used?: string[];
  sources?: Array<{ filename: string; page_number: number; citation: string }>;
};

type AnalysisResult = {
  analysis_id: string;
  period: { start_date: string; end_date: string };
  currency: string;
  data_analyst: DataAnalystReport;
  business_analyst: BusinessAnalystReport;
  answer: string;
  disclaimer: string;
};

const money = (value: number | null | undefined, currency = 'INR') => {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Not available';
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString('en-IN')}`;
  }
};

const percent = (value: number | null | undefined) =>
  value === null || value === undefined ? 'N/A' : `${value.toFixed(1)}%`;

export default function IntelligencePage() {
  const [question, setQuestion] = useState('Review our financial and operational performance. What should management prioritise next?');
  const [startDate, setStartDate] = useState('2026-08-01');
  const [endDate, setEndDate] = useState('2026-10-31');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const analyse = async () => {
    if (loading || question.trim().length < 5 || !startDate || !endDate || endDate < startDate) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/intelligence/analyse', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-ID': DEMO_ORGANIZATION_ID,
        },
        body: JSON.stringify({
          question: question.trim(),
          start_date: startDate,
          end_date: endDate,
          max_tool_rounds: 6,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof payload.detail === 'string' ? payload.detail : `Analysis failed (${response.status})`);
      }
      setResult(payload as AnalysisResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The analysis could not be completed.');
    } finally {
      setLoading(false);
    }
  };

  const report = result?.data_analyst;
  const business = result?.business_analyst;
  const metrics = report?.metrics || {};

  return (
    <div className="intelligence-page">
      <div className="intelligence-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> TWO-STAGE BUSINESS INTELLIGENCE</div>
          <h1>One question. Two specialist perspectives.</h1>
          <p>ProfitPulse first establishes what the data says, then interprets what the business should do next.</p>
        </div>
        <div className="intelligence-status"><span className="pulse-dot" /> Manufacturing workspace</div>
      </div>

      <section className="intelligence-command panel">
        <div className="intelligence-command-top">
          <div className="intelligence-command-icon"><Sparkles size={20} /></div>
          <div>
            <strong>Start a business investigation</strong>
            <span>Choose a reporting period and ask a question about your company.</span>
          </div>
        </div>
        <label className="intelligence-question-label" htmlFor="intelligence-question">WHAT WOULD YOU LIKE TO UNDERSTAND?</label>
        <textarea
          id="intelligence-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
          placeholder="For example: Revenue increased, but profitability fell. What should we investigate?"
        />
        <div className="intelligence-form-footer">
          <div className="intelligence-dates">
            <label><CalendarDays size={14} /> From <input type="date" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <span>to</span>
            <label> <input type="date" value={endDate} min={startDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          </div>
          <button className="intelligence-run-button" type="button" onClick={() => void analyse()} disabled={loading || question.trim().length < 5 || endDate < startDate}>
            {loading ? <><LoaderCircle size={16} className="spin" /> Analysing</> : <><Play size={15} fill="currentColor" /> Run analysis</>}
          </button>
        </div>
        {error && <div className="intelligence-error"><CircleAlert size={15} /> {error}</div>}
      </section>

      <div className="agent-pipeline">
        <article className={`agent-stage agent-stage-data ${report ? 'agent-stage-complete' : ''}`}>
          <div className="agent-stage-top">
            <div className="agent-stage-icon"><FileSearch size={20} /></div>
            <span className="agent-stage-number">01 / ANALYSE</span>
          </div>
          <h2>AI Data Analyst</h2>
          <p>Finds the facts in your ledger and operating records. Calculations are deterministic, not generated by the language model.</p>
          <div className="agent-stage-tags"><span>SQL & ledger</span><span>Financial metrics</span><span>Inventory</span><span>Product performance</span></div>
          <div className="agent-stage-footer">
            {report ? <><CheckCircle2 size={15} /> Findings ready</> : <><Activity size={15} /> Waiting for analysis</>}
          </div>
        </article>
        <div className="agent-handoff"><ArrowRight size={19} /><span>Verified findings<br />+ evidence</span></div>
        <article className={`agent-stage agent-stage-business ${business ? 'agent-stage-complete' : ''}`}>
          <div className="agent-stage-top">
            <div className="agent-stage-icon"><Target size={20} /></div>
            <span className="agent-stage-number">02 / INTERPRET</span>
          </div>
          <h2>AI Business Analyst</h2>
          <p>Turns verified findings into business implications, prioritised actions and questions management should investigate.</p>
          <div className="agent-stage-tags"><span>Business diagnosis</span><span>Priorities</span><span>Recommendations</span></div>
          <div className="agent-stage-footer">
            {business ? <><CheckCircle2 size={15} /> Recommendations ready</> : <><Bot size={15} /> Waiting for findings</>}
          </div>
        </article>
      </div>

      {result && report && business && (
        <div className="intelligence-results">
          <div className="intelligence-results-heading">
            <div><div className="eyebrow"><span className="eyebrow-line" /> COMBINED INTELLIGENCE REPORT</div><h2>Business performance briefing</h2><p>{startDate} to {endDate} · {report.summary}</p></div>
            <span className="status-pill status-good"><CheckCircle2 size={12} /> Analysis complete</span>
          </div>

          <div className="intelligence-metric-grid">
            <div className="intelligence-metric"><span>Net revenue</span><strong>{money(metrics.net_revenue, report.currency)}</strong><small>Selected period</small></div>
            <div className="intelligence-metric"><span>Gross profit</span><strong>{money(metrics.gross_profit, report.currency)}</strong><small>{percent(metrics.gross_margin_pct)} gross margin</small></div>
            <div className="intelligence-metric"><span>EBITDA</span><strong className={Number(metrics.ebitda) < 0 ? 'metric-negative' : ''}>{money(metrics.ebitda, report.currency)}</strong><small>{percent(metrics.ebitda_margin_pct)} EBITDA margin</small></div>
            <div className="intelligence-metric"><span>Operating expenses</span><strong>{money(metrics.operating_expenses, report.currency)}</strong><small>{percent(metrics.operating_expense_ratio_pct)} of net revenue</small></div>
          </div>

          <div className="intelligence-report-grid">
            <section className="panel intelligence-findings">
              <div className="intelligence-panel-heading"><div className="intelligence-panel-icon data-icon"><FileSearch size={17} /></div><div><h3>Data Analyst findings</h3><span>Measured facts and supporting evidence</span></div></div>
              <div className="finding-list">
                {report.findings.map((finding) => (
                  <article className="finding-item" key={finding.id}>
                    <div className={`finding-severity severity-${finding.severity}`} />
                    <div><strong>{finding.title}</strong><p>{finding.detail}</p><small>{finding.evidence}</small></div>
                  </article>
                ))}
              </div>
              <div className="intelligence-source-note"><ShieldCheck size={14} /> Sources: {report.data_sources.join(' · ')}</div>
            </section>
            <section className="panel intelligence-business-report">
              <div className="intelligence-panel-heading"><div className="intelligence-panel-icon business-icon"><Target size={17} /></div><div><h3>Business Analyst recommendations</h3><span>Interpretation and action priorities</span></div></div>
              <div className="markdown-content intelligence-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{business.answer || result.answer}</ReactMarkdown></div>
              {business.sources && business.sources.length > 0 && <div className="intelligence-citations"><strong>Company documents referenced</strong>{business.sources.map((source, index) => <span key={`${source.filename}-${source.page_number}-${index}`}>{source.citation || `${source.filename}, p. ${source.page_number}`}</span>)}</div>}
              <div className="intelligence-source-note"><ShieldCheck size={14} /> Human approval required before operational changes are made.</div>
            </section>
          </div>
          <div className="intelligence-disclaimer">{result.disclaimer}</div>
        </div>
      )}

      {!result && (
        <div className="intelligence-empty">
          <div className="intelligence-empty-icon"><TrendingUp size={21} /></div>
          <div><strong>Your combined report will appear here</strong><span>Run an analysis to see the Data Analyst's evidence and the Business Analyst's recommendations side by side.</span></div>
        </div>
      )}
    </div>
  );
}
