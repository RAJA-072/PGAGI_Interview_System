import { useEffect, useState } from 'react'
import { fetchRoles, startInterview, submitAnswer, fetchSummary } from './api'

const STAGES = {
  UPLOAD: 'upload',
  INTERVIEW: 'interview',
  SUMMARY: 'summary',
}

export default function App() {
  const [stage, setStage] = useState(STAGES.UPLOAD)
  const [roles, setRoles] = useState([])
  const [selectedRole, setSelectedRole] = useState('')
  const [resumeFile, setResumeFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [sessionId, setSessionId] = useState(null)
  const [candidateName, setCandidateName] = useState('')
  const [extractedSkills, setExtractedSkills] = useState([])
  const [questionNumber, setQuestionNumber] = useState(1)
  const [maxQuestions, setMaxQuestions] = useState(5)
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [sourceChunks, setSourceChunks] = useState([])
  const [answer, setAnswer] = useState('')
  const [showSources, setShowSources] = useState(false)

  const [qaHistory, setQaHistory] = useState([]) // {question, answer}
  const [reportData, setReportData] = useState(null)

  useEffect(() => {
    fetchRoles()
      .then((data) => {
        setRoles(data)
        if (data.length) setSelectedRole(data[0].id)
      })
      .catch((err) => setError(`Could not load roles: ${err.message}`))
  }, [])

  async function handleStart(e) {
    e.preventDefault()
    if (!resumeFile || !selectedRole) return
    setLoading(true)
    setError('')
    try {
      const data = await startInterview(selectedRole, resumeFile)
      setSessionId(data.session_id)
      setCandidateName(data.candidate_name || '')
      setExtractedSkills(data.extracted_skills)
      setQuestionNumber(data.question_number)
      setMaxQuestions(data.max_questions)
      setCurrentQuestion(data.question)
      setSourceChunks(data.source_chunks)
      setStage(STAGES.INTERVIEW)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmitAnswer(e) {
    e.preventDefault()
    if (!answer.trim()) return
    setLoading(true)
    setError('')
    try {
      const finishedQaEntry = { question: currentQuestion, answer }
      const data = await submitAnswer(sessionId, answer)
      setQaHistory((prev) => [...prev, finishedQaEntry])
      setAnswer('')
      setShowSources(false)

      if (data.done) {
        const summaryData = await fetchSummary(sessionId)
        setReportData(summaryData)
        setStage(STAGES.SUMMARY)
      } else {
        setQuestionNumber(data.question_number)
        setCurrentQuestion(data.question)
        setSourceChunks(data.source_chunks)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleRestart() {
    setStage(STAGES.UPLOAD)
    setResumeFile(null)
    setSessionId(null)
    setCandidateName('')
    setQaHistory([])
    setReportData(null)
    setError('')
    setAnswer('')
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Candidate Screening</h1>
        <p className="subtitle">Resume-aware, role-specific technical interview powered by RAG</p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {stage === STAGES.UPLOAD && (
        <UploadStage
          roles={roles}
          selectedRole={selectedRole}
          setSelectedRole={setSelectedRole}
          resumeFile={resumeFile}
          setResumeFile={setResumeFile}
          onSubmit={handleStart}
          loading={loading}
        />
      )}

      {stage === STAGES.INTERVIEW && (
        <InterviewStage
          questionNumber={questionNumber}
          maxQuestions={maxQuestions}
          currentQuestion={currentQuestion}
          sourceChunks={sourceChunks}
          showSources={showSources}
          setShowSources={setShowSources}
          answer={answer}
          setAnswer={setAnswer}
          onSubmit={handleSubmitAnswer}
          loading={loading}
          candidateName={candidateName}
          extractedSkills={extractedSkills}
          qaHistory={qaHistory}
        />
      )}

      {stage === STAGES.SUMMARY && (
        <SummaryStage reportData={reportData} onRestart={handleRestart} />
      )}
    </div>
  )
}

function UploadStage({ roles, selectedRole, setSelectedRole, resumeFile, setResumeFile, onSubmit, loading }) {
  return (
    <form className="card" onSubmit={onSubmit}>
      <h2>Start a new interview</h2>

      <label className="field">
        <span>Target role</span>
        <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)} required>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Resume (PDF or TXT)</span>
        <input
          type="file"
          accept=".pdf,.txt"
          onChange={(e) => setResumeFile(e.target.files[0])}
          required
        />
      </label>

      <button type="submit" disabled={loading || !resumeFile}>
        {loading ? 'Analyzing resume…' : 'Start Interview'}
      </button>
    </form>
  )
}

function InterviewStage({
  questionNumber,
  maxQuestions,
  currentQuestion,
  sourceChunks,
  showSources,
  setShowSources,
  answer,
  setAnswer,
  onSubmit,
  loading,
  candidateName,
  extractedSkills,
  qaHistory,
}) {
  return (
    <div className="card">
      <div className="progress-row">
        <span>
          Question {questionNumber} of {maxQuestions}
        </span>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${(questionNumber / maxQuestions) * 100}%` }}
          />
        </div>
      </div>

      {(candidateName || extractedSkills.length > 0) && (
        <div className="skills-row">
          {candidateName && <span className="candidate-name-pill">{candidateName}</span>}
          {extractedSkills.slice(0, 8).map((s, i) => (
            <span key={i} className="skill-pill">
              {s}
            </span>
          ))}
        </div>
      )}

      <h3 className="question-text">{currentQuestion}</h3>

      {sourceChunks.length > 0 && (
        <div className="sources-block">
          <button type="button" className="link-button" onClick={() => setShowSources(!showSources)}>
            {showSources ? 'Hide' : 'Show'} retrieved context ({sourceChunks.length})
          </button>
          {showSources && (
            <div className="sources-list">
              {sourceChunks.map((chunk, i) => (
                <p key={i} className="source-chunk">
                  {chunk}…
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      <form onSubmit={onSubmit}>
        <textarea
          rows={5}
          placeholder="Type your answer…"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          required
        />
        <button type="submit" disabled={loading || !answer.trim()}>
          {loading ? 'Thinking…' : questionNumber >= maxQuestions ? 'Submit & Finish' : 'Submit & Next Question'}
        </button>
      </form>

      {qaHistory.length > 0 && (
        <details className="history-block">
          <summary>Previous answers ({qaHistory.length})</summary>
          {qaHistory.map((qa, i) => (
            <div key={i} className="history-item">
              <p className="history-q">Q{i + 1}: {qa.question}</p>
              <p className="history-a">{qa.answer}</p>
            </div>
          ))}
        </details>
      )}
    </div>
  )
}

function ScoreBadge({ score }) {
  const color = score >= 8 ? '#1a7f3c' : score >= 5 ? '#b45309' : '#b3261e'
  const bg = score >= 8 ? '#d1fadf' : score >= 5 ? '#fef3c7' : '#fdecea'
  return (
    <span className="score-badge" style={{ color, background: bg }}>
      {score}/10
    </span>
  )
}

function VerdictPill({ verdict }) {
  const colorMap = {
    Strong: { color: '#1a7f3c', bg: '#d1fadf' },
    Adequate: { color: '#b45309', bg: '#fef3c7' },
    'Needs Improvement': { color: '#b3261e', bg: '#fdecea' },
  }
  const style = colorMap[verdict] || colorMap['Adequate']
  return (
    <span className="verdict-pill" style={{ color: style.color, background: style.bg }}>
      {verdict}
    </span>
  )
}

function SummaryStage({ reportData, onRestart }) {
  if (!reportData) return null
  const { candidate_name, role, overall_score, overall_impression, report_questions, strengths, improvements, next_steps } = reportData

  return (
    <div className="card">
      <div className="report-header">
        <div>
          <h2 style={{ margin: 0 }}>Interview Report</h2>
          {candidate_name && <p className="report-meta">{candidate_name} &mdash; {role}</p>}
        </div>
        <div className="overall-score-circle" style={{
          background: overall_score >= 8 ? '#d1fadf' : overall_score >= 5 ? '#fef3c7' : '#fdecea',
          color: overall_score >= 8 ? '#1a7f3c' : overall_score >= 5 ? '#b45309' : '#b3261e',
        }}>
          <span className="overall-score-num">{overall_score}</span>
          <span className="overall-score-label">/10</span>
        </div>
      </div>

      {overall_impression && (
        <p className="overall-impression">{overall_impression}</p>
      )}

      <h3 className="report-section-title">Question-by-Question Breakdown</h3>
      {report_questions && report_questions.map((rq) => (
        <div key={rq.number} className="report-question-block">
          <div className="report-q-header">
            <span className="report-q-num">Q{rq.number}</span>
            <span className="report-q-text">{rq.question}</span>
            <ScoreBadge score={rq.score} />
            <VerdictPill verdict={rq.verdict} />
          </div>
          <div className="report-answer-block">
            <span className="report-answer-label">Candidate&apos;s answer:</span>
            <p className="report-answer-text">{rq.candidate_answer || '(no answer given)'}</p>
          </div>
          {rq.feedback && (
            <p className="report-feedback">{rq.feedback}</p>
          )}
        </div>
      ))}

      <div className="report-two-col">
        {strengths && strengths.length > 0 && (
          <div className="report-col strengths-col">
            <h4>Strengths</h4>
            <ul>
              {strengths.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        )}
        {improvements && improvements.length > 0 && (
          <div className="report-col improvements-col">
            <h4>Areas to Improve</h4>
            <ul>
              {improvements.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        )}
      </div>

      {next_steps && (
        <div className="report-next-steps">
          <strong>Next Steps:</strong> {next_steps}
        </div>
      )}

      <button onClick={onRestart} style={{ marginTop: '24px' }}>Start a new interview</button>
    </div>
  )
}
