import React, { useState } from 'react';
import './EnglishGrammarView.less';

const EnglishGrammarView = ({
  agent,
  mode,
  userInput,
  onInputChange,
  onRun,
  loading,
  result,
  reviewMode,
}) => {
  const [activeTab, setActiveTab] = useState('pedagogical');
  const [exportFormat, setExportFormat] = useState('json');

  const handleAnalyze = () => {
    onRun({ export_format: exportFormat });
  };

  const handleDownload = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  // AgentWorkbench passes API payload { result: agentOutput, ... }
  const runResult = result?.result || result || {};
  const linguistic = runResult.linguistic || {};
  const pedagogical = runResult.pedagogical || {};
  const warnings = runResult.warnings || {};
  const exportData = runResult.export || {};

  const renderTokensTable = () => {
    const tokens = linguistic.tokens || [];
    if (tokens.length === 0) return <div className="empty-state">No tokens to display</div>;

    return (
      <div className="tokens-table-wrapper">
        <table className="tokens-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Text</th>
              <th>Lemma</th>
              <th>POS</th>
              <th>Tag</th>
              <th>Dep</th>
              <th>Head</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((token, idx) => (
              <tr key={idx}>
                <td>{token.index}</td>
                <td className="token-text">{token.text}</td>
                <td>{token.lemma}</td>
                <td>{token.pos}</td>
                <td className="token-tag">{token.tag}</td>
                <td className="token-dep">{token.dep}</td>
                <td>{token.head_idx}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderNounChunks = () => {
    const chunks = linguistic.noun_chunks || [];
    if (chunks.length === 0) return null;

    return (
      <div className="noun-chunks-section">
        <h4>Noun Phrases</h4>
        <div className="chunks-list">
          {chunks.map((chunk, idx) => (
            <span key={idx} className="chunk-tag">
              {chunk.text}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const renderDependencyViz = () => {
    const displacy = linguistic.displacy_data;
    if (!displacy || !displacy.words) return <div className="empty-state">No dependency data</div>;

    return (
      <div className="dependency-viz">
        <div className="dep-sentence">
          {displacy.words.map((word, idx) => (
            <div key={idx} className="dep-word">
              <span className="word-text">{word.text}</span>
              <span className="word-tag">{word.tag}</span>
            </div>
          ))}
        </div>
        <div className="dep-arcs-info">
          <h4>Dependencies</h4>
          <ul>
            {(displacy.arcs || []).slice(0, 15).map((arc, idx) => {
              const from = displacy.words[arc.start]?.text || arc.start;
              const to = displacy.words[arc.end]?.text || arc.end;
              return (
                <li key={idx}>
                  <span className="arc-label">{arc.label}</span>: {from} → {to}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    );
  };

  const ROLE_LABELS = {
    subject: '主语',
    predicate: '谓语',
    object: '宾语',
    complement: '补语',
    adverbial: '状语',
    adverbials: '状语',
    modifier: '修饰语',
    modifiers: '修饰语',
    true_subject: '真主语',
    antecedent: '先行词',
    subordinator: '从属连词',
    relative_pronoun: '关系代词',
    preposition: '介词',
    auxiliary: '助动词',
    verb: '动词',
    head: '中心词',
    type: '类型',
    text: '文本',
    function: '功能',
    comparison: '比较结构',
    comparison_marker: '比较标记',
    comparison_object: '比较对象',
    object_complement: '宾语补足语',
    post_modifier: '后置修饰',
    conjunction: '连词',
  };

  const asList = (value) => {
    if (value == null) return [];
    return Array.isArray(value) ? value : [value];
  };

  const formatPlain = (value) => {
    if (value == null || value === '') return null;
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    if (Array.isArray(value)) {
      const parts = value.map(formatPlain).filter(Boolean);
      return parts.length ? parts.join(' / ') : null;
    }
    if (typeof value === 'object') {
      if (value.text) {
        const typeHint = value.type ? `〔${value.type}〕` : '';
        return `${value.text}${typeHint}`;
      }
      if (value.verb) {
        const aux = value.auxiliary ? `${value.auxiliary} ` : '';
        return `${aux}${value.verb}`;
      }
      if (value.preposition && value.object) {
        const obj = typeof value.object === 'string' ? value.object : formatPlain(value.object);
        return `${value.preposition} ${obj || ''}`.trim();
      }
      if (value.head) return String(value.head);
      return null;
    }
    return null;
  };

  const nestedEntries = (value) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];

    const preferred = [
      'type', 'text', 'verb', 'auxiliary', 'head', 'subordinator', 'relative_pronoun',
      'preposition', 'function', 'subject', 'predicate', 'object', 'complement',
      'modifier', 'modifiers', 'adverbials', 'post_modifier', 'comparison',
      'comparison_marker', 'comparison_object', 'object_complement', 'conjunction',
      'true_subject', 'antecedent',
    ];

    const entries = [];
    const seen = new Set();
    for (const key of preferred) {
      if (value[key] == null || value[key] === '') continue;
      seen.add(key);
      entries.push([key, value[key]]);
    }
    for (const [key, val] of Object.entries(value)) {
      if (seen.has(key) || val == null || val === '') continue;
      if (['status', 'validation_errors', 'original'].includes(key)) continue;
      entries.push([key, val]);
    }
    return entries;
  };

  const renderConstituent = (role, value, depth, key) => {
    if (value == null || value === '') return null;

    const label = ROLE_LABELS[role] || role;
    const items = asList(value);
    const canNest = depth < 2;

    return items.map((item, itemIdx) => {
      const summary = formatPlain(item);
      const children = canNest && typeof item === 'object' && item !== null
        ? nestedEntries(item)
        : [];

      // Skip nesting pure scalar wrappers that only duplicate the summary
      const usefulChildren = children.filter(([childKey, childVal]) => {
        if (['text', 'verb'].includes(childKey) && summary) return false;
        if (childKey === 'type' && typeof item === 'object' && item.text && summary?.includes('〔')) return false;
        return childVal != null && childVal !== '';
      });

      return (
        <div key={`${key}-${itemIdx}`} className={`constituent depth-${depth}`}>
          <div className="constituent-main">
            <span className={`role-tag role-${role}`}>{label}</span>
            <span className="constituent-text">
              {summary || (typeof item === 'object' ? (item.type || '（复合结构）') : String(item))}
            </span>
          </div>
          {usefulChildren.length > 0 && (
            <div className="constituent-children">
              {usefulChildren.map(([childKey, childVal]) =>
                renderConstituent(childKey, childVal, depth + 1, `${key}-${itemIdx}-${childKey}`)
              )}
            </div>
          )}
        </div>
      );
    });
  };

  const renderClauseTree = (clause, idx) => {
    const slots = [
      ['subordinator', clause.subordinator],
      ['relative_pronoun', clause.relative_pronoun],
      ['preposition', clause.preposition],
      ['subject', clause.subject],
      ['predicate', clause.predicate],
      ['object', clause.object],
      ['complement', clause.complement],
      ['true_subject', clause.true_subject],
      ['adverbials', clause.adverbials],
      ['antecedent', clause.antecedent],
    ];

    return (
      <div key={idx} className="clause-item">
        <div className="clause-header">
          <span className="clause-type">{clause.clause_type || 'clause'}</span>
          <span className="clause-index">从句 {idx + 1}</span>
        </div>
        <div className="clause-body constituents">
          {slots.map(([role, value]) => renderConstituent(role, value, 1, `c${idx}-${role}`))}
        </div>
      </div>
    );
  };

  const renderPedagogical = () => {
    if (pedagogical.status === 'unavailable') {
      return <div className="status-message">LLM unavailable. Only linguistic analysis shown.</div>;
    }

    if (pedagogical.status !== 'success') {
      return <div className="status-message error">Pedagogical analysis failed: {pedagogical.message}</div>;
    }

    const clauses = pedagogical.clauses || [];

    return (
      <div className="pedagogical-view">
        <div className="sentence-type">
          <strong>句型：</strong> {pedagogical.type}
        </div>

        <div className="clauses-section">
          <h4>句子成分（Clauses · {clauses.length}）</h4>
          <p className="constituent-hint">按主语 / 谓语 / 宾语 / 补语 / 状语等标记，最多展开两层。</p>
          {clauses.map(renderClauseTree)}
        </div>

        {pedagogical.relations && (
          <div className="relations-section">
            <h4>成分关系</h4>
            <p>{pedagogical.relations}</p>
          </div>
        )}
      </div>
    );
  };

  const renderWarnings = () => {
    const warningsList = warnings.warnings || [];
    if (warningsList.length === 0) {
      return <div className="empty-state">No grammar warnings detected</div>;
    }

    return (
      <div className="warnings-list">
        <div className="warnings-header">
          <span>Checker: {warnings.checker_used}</span>
        </div>
        {warningsList.map((warning, idx) => (
          <div key={idx} className="warning-item">
            <div className="warning-message">{warning.message}</div>
            {warning.suggestions && warning.suggestions.length > 0 && (
              <div className="warning-suggestions">
                Suggestions: {warning.suggestions.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="english-grammar-view">
      <div className="input-section">
        <textarea
          className="sentence-input"
          placeholder="Enter an English sentence to analyze..."
          value={userInput}
          onChange={(e) => onInputChange(e.target.value)}
          disabled={reviewMode || loading}
          rows={3}
        />
        <div className="input-controls">
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value)}
            disabled={reviewMode || loading}
          >
            <option value="json">JSON Export</option>
            <option value="csv">CSV Export</option>
          </select>
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={reviewMode || loading || !userInput.trim()}
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {result && (
        <>
          <div className="tabs">
            <button
              className={activeTab === 'pedagogical' ? 'active' : ''}
              onClick={() => setActiveTab('pedagogical')}
            >
              Pedagogical Structure
            </button>
            <button
              className={activeTab === 'linguistic' ? 'active' : ''}
              onClick={() => setActiveTab('linguistic')}
            >
              Linguistic Analysis
            </button>
            <button
              className={activeTab === 'warnings' ? 'active' : ''}
              onClick={() => setActiveTab('warnings')}
            >
              Warnings ({(warnings.warnings || []).length})
            </button>
          </div>

          <div className="tab-content">
            {activeTab === 'pedagogical' && renderPedagogical()}
            {activeTab === 'linguistic' && (
              <div className="linguistic-view">
                {renderNounChunks()}
                {renderTokensTable()}
                {renderDependencyViz()}
              </div>
            )}
            {activeTab === 'warnings' && renderWarnings()}
          </div>

          {exportData && (exportData.json || exportData.csv) && (
            <div className="export-section">
              <button
                className="download-btn"
                onClick={() => {
                  const content = exportData.json || exportData.csv;
                  const ext = exportData.json ? 'json' : 'csv';
                  handleDownload(content, `grammar-analysis.${ext}`);
                }}
              >
                Download {exportFormat.toUpperCase()}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default EnglishGrammarView;
