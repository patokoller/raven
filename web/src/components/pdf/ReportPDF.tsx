import {
  Document, Page, Text, View, StyleSheet, Font
} from '@react-pdf/renderer'

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  page: {
    fontFamily: 'Helvetica',
    fontSize: 9,
    color: '#1a1a1a',
    paddingTop: 52,
    paddingBottom: 52,
    paddingHorizontal: 52,
    backgroundColor: '#FDFAF5',
  },

  // Cover
  coverPage: {
    fontFamily: 'Helvetica',
    backgroundColor: '#0D0F0E',
    padding: 0,
  },
  coverContent: {
    flex: 1,
    padding: 60,
    justifyContent: 'space-between',
  },
  coverEyebrow: {
    fontSize: 7,
    color: 'rgba(245,240,232,0.35)',
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: 80,
  },
  coverTitle: {
    fontSize: 36,
    color: '#F5F0E8',
    fontFamily: 'Helvetica-Bold',
    lineHeight: 1.15,
    marginBottom: 16,
  },
  coverSubtitle: {
    fontSize: 11,
    color: 'rgba(245,240,232,0.5)',
    marginBottom: 60,
  },
  coverMeta: {
    flexDirection: 'row',
    gap: 32,
    marginBottom: 60,
  },
  coverMetaItem: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(245,240,232,0.1)',
    paddingTop: 10,
    minWidth: 100,
  },
  coverMetaLabel: {
    fontSize: 6.5,
    color: 'rgba(245,240,232,0.3)',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  coverMetaValue: {
    fontSize: 9,
    color: 'rgba(245,240,232,0.7)',
  },
  coverFooter: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(245,240,232,0.08)',
    paddingTop: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  coverFooterText: {
    fontSize: 7,
    color: 'rgba(245,240,232,0.2)',
  },
  goldAccent: {
    color: '#C9A84C',
  },

  // Section header
  sectionHeader: {
    borderBottomWidth: 0.5,
    borderBottomColor: '#D8D2C6',
    paddingBottom: 6,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    fontSize: 7,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    color: '#6B6560',
    fontFamily: 'Helvetica-Bold',
  },

  // Body text
  body: {
    fontSize: 9,
    lineHeight: 1.65,
    color: '#2A2E2C',
    marginBottom: 8,
  },
  bodySmall: {
    fontSize: 8,
    lineHeight: 1.6,
    color: '#4A4A4A',
    marginBottom: 6,
  },

  // Risk indicator badge
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 2,
    marginBottom: 12,
    alignSelf: 'flex-start',
  },
  badgeText: {
    fontSize: 7,
    letterSpacing: 1,
    fontFamily: 'Helvetica-Bold',
  },

  // Sub-heading
  subHeading: {
    fontSize: 7.5,
    fontFamily: 'Helvetica-Bold',
    color: '#1a1a1a',
    marginTop: 10,
    marginBottom: 5,
    letterSpacing: 0.5,
  },

  // Finding bullet
  finding: {
    flexDirection: 'row',
    marginBottom: 4,
    paddingLeft: 2,
  },
  findingBullet: {
    fontSize: 9,
    color: '#C9A84C',
    marginRight: 6,
    marginTop: 0.5,
  },
  findingText: {
    fontSize: 8.5,
    color: '#2A2E2C',
    lineHeight: 1.5,
    flex: 1,
  },

  // Action card
  actionCard: {
    backgroundColor: '#F0EBE2',
    borderRadius: 3,
    padding: 8,
    marginBottom: 6,
    flexDirection: 'row',
    gap: 8,
  },
  actionPriority: {
    fontSize: 6,
    letterSpacing: 1,
    fontFamily: 'Helvetica-Bold',
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 2,
    alignSelf: 'flex-start',
  },
  actionContent: {
    flex: 1,
  },
  actionTitle: {
    fontSize: 8.5,
    fontFamily: 'Helvetica-Bold',
    color: '#1a1a1a',
    marginBottom: 2,
  },
  actionMeta: {
    fontSize: 7.5,
    color: '#6B6560',
  },

  // Metric grid
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
    marginBottom: 8,
  },
  metricCard: {
    backgroundColor: '#F0EBE2',
    borderRadius: 3,
    padding: 10,
    width: '47%',
  },
  metricLabel: {
    fontSize: 6.5,
    letterSpacing: 1,
    textTransform: 'uppercase',
    color: '#6B6560',
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 10,
    fontFamily: 'Helvetica-Bold',
    color: '#1a1a1a',
  },
  metricSub: {
    fontSize: 7,
    color: '#6B6560',
    marginTop: 2,
  },

  // Watchlist tag
  tag: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 2,
    marginRight: 4,
    marginBottom: 4,
  },
  tagText: {
    fontSize: 7,
    color: '#92400E',
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 4,
  },

  // Divider
  divider: {
    borderBottomWidth: 0.5,
    borderBottomColor: '#D8D2C6',
    marginVertical: 10,
  },

  // Disclaimer
  disclaimer: {
    fontSize: 7,
    color: '#9A9490',
    lineHeight: 1.6,
    marginTop: 8,
    fontStyle: 'italic',
  },

  // Page footer
  pageFooter: {
    position: 'absolute',
    bottom: 28,
    left: 52,
    right: 52,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 0.5,
    borderTopColor: '#D8D2C6',
    paddingTop: 8,
  },
  pageFooterText: {
    fontSize: 7,
    color: '#9A9490',
  },

  // Table of contents
  tocItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 5,
    borderBottomWidth: 0.5,
    borderBottomColor: '#EDE8DF',
  },
  tocNum: {
    fontSize: 7.5,
    color: '#C9A84C',
    fontFamily: 'Helvetica-Bold',
    marginRight: 8,
    width: 16,
  },
  tocLabel: {
    fontSize: 9,
    color: '#2A2E2C',
    flex: 1,
  },
  tocDots: {
    fontSize: 7,
    color: '#D8D2C6',
    flex: 1,
    textAlign: 'center',
  },
  tocPage: {
    fontSize: 7.5,
    color: '#9A9490',
  },
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function PageFooter({ reportRef, period }: { reportRef: string; period: string }) {
  return (
    <View style={styles.pageFooter} fixed>
      <Text style={styles.pageFooterText}>Raven Risk Intelligence · {reportRef} · {period}</Text>
      <Text style={styles.pageFooterText} render={({ pageNumber, totalPages }) =>
        `${pageNumber} / ${totalPages}`
      } />
      <Text style={styles.pageFooterText}>Confidential</Text>
    </View>
  )
}

function SectionTitle({ num, title }: { num: string; title: string }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{num} · {title}</Text>
    </View>
  )
}

function RiskBadge({ indicator }: { indicator: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    GREEN: { bg: '#DCFCE7', text: '#166534' },
    AMBER: { bg: '#FEF3C7', text: '#92400E' },
    RED:   { bg: '#FEE2E2', text: '#991B1B' },
  }
  const c = colors[indicator] ?? colors.AMBER
  return (
    <View style={[styles.badge, { backgroundColor: c.bg }]}>
      <Text style={[styles.badgeText, { color: c.text }]}>{indicator} RISK</Text>
    </View>
  )
}

function BodyText({ children }: { children: string }) {
  if (!children) return null
  return <Text style={styles.body}>{children}</Text>
}

function SubHeading({ children }: { children: string }) {
  return <Text style={styles.subHeading}>{children}</Text>
}

function Findings({ items }: { items: string[] }) {
  if (!items?.length) return null
  return (
    <View>
      {items.map((item, i) => (
        <View key={i} style={styles.finding}>
          <Text style={styles.findingBullet}>›</Text>
          <Text style={styles.findingText}>{item}</Text>
        </View>
      ))}
    </View>
  )
}

function ActionCard({ action }: { action: any }) {
  if (!action) return null
  const isHigh = action.priority === 'HIGH'
  const isMed  = action.priority === 'MEDIUM'
  return (
    <View style={styles.actionCard}>
      <View style={[styles.actionPriority, {
        backgroundColor: isHigh ? '#FEE2E2' : isMed ? '#FEF3C7' : '#E5E7EB',
        color: isHigh ? '#991B1B' : isMed ? '#92400E' : '#6B7280',
      }]}>
        <Text style={{ fontSize: 6, letterSpacing: 1, fontFamily: 'Helvetica-Bold',
          color: isHigh ? '#991B1B' : isMed ? '#92400E' : '#6B7280' }}>
          {action.priority || '!'}
        </Text>
      </View>
      <View style={styles.actionContent}>
        <Text style={styles.actionTitle}>{action.action || action}</Text>
        {action.timeline && <Text style={styles.actionMeta}>Timeline: {action.timeline}</Text>}
        {action.rationale && <Text style={[styles.actionMeta, { marginTop: 2 }]}>{action.rationale}</Text>}
      </View>
    </View>
  )
}

// ── Report document ───────────────────────────────────────────────────────────

interface ReportPDFProps {
  report: any
  clientName?: string
}

export function ReportPDF({ report, clientName }: ReportPDFProps) {
  const s1 = report.section_executive_summary
  const s2 = report.section_portfolio_composition
  const s3 = report.section_risk_scorecard
  const s4 = report.section_counterparty_analysis
  const s5 = report.section_stress_test_results
  const s6 = report.section_recommendations
  const reportDate = new Date().toLocaleDateString('en-CH', { day: '2-digit', month: 'long', year: 'numeric' })

  return (
    <Document
      title={report.title}
      author="Raven Risk Intelligence"
      subject={`${report.report_period} Counterparty Risk Report`}
      keywords="risk, counterparty, portfolio, FINMA, Switzerland"
    >
      {/* ── COVER PAGE ── */}
      <Page size="A4" style={styles.coverPage}>
        <View style={styles.coverContent}>
          <View>
            <Text style={styles.coverEyebrow}>Raven · Risk & Portfolio Intelligence · Confidential</Text>
            <Text style={styles.coverTitle}>{report.title || 'Risk Report'}</Text>
            <Text style={styles.coverSubtitle}>
              {s1?.headline || 'Institutional Counterparty Risk Assessment'}
            </Text>

            {s1?.risk_indicator && (
              <View style={{ marginBottom: 40 }}>
                <View style={[styles.badge, {
                  backgroundColor: s1.risk_indicator === 'GREEN' ? 'rgba(34,197,94,0.15)' :
                    s1.risk_indicator === 'RED' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)'
                }]}>
                  <Text style={[styles.badgeText, {
                    color: s1.risk_indicator === 'GREEN' ? '#4ade80' :
                      s1.risk_indicator === 'RED' ? '#f87171' : '#fbbf24'
                  }]}>
                    {s1.risk_indicator} RISK PROFILE
                  </Text>
                </View>
              </View>
            )}

            <View style={styles.coverMeta}>
              <View style={styles.coverMetaItem}>
                <Text style={styles.coverMetaLabel}>Client</Text>
                <Text style={styles.coverMetaValue}>{clientName || 'Helvetic Capital AG'}</Text>
              </View>
              <View style={styles.coverMetaItem}>
                <Text style={styles.coverMetaLabel}>Period</Text>
                <Text style={styles.coverMetaValue}>{report.report_period}</Text>
              </View>
              <View style={styles.coverMetaItem}>
                <Text style={styles.coverMetaLabel}>Reference</Text>
                <Text style={styles.coverMetaValue}>{report.report_ref}</Text>
              </View>
              <View style={styles.coverMetaItem}>
                <Text style={styles.coverMetaLabel}>Report Date</Text>
                <Text style={styles.coverMetaValue}>{reportDate}</Text>
              </View>
            </View>
          </View>

          <View style={styles.coverFooter}>
            <View>
              <Text style={styles.coverFooterText}>RAVEN RISK INTELLIGENCE</Text>
              <Text style={[styles.coverFooterText, { marginTop: 2 }]}>Swiss Digital Asset Wealth Management</Text>
            </View>
            <Text style={styles.coverFooterText}>FINMA-Aligned · Institutional Grade</Text>
          </View>
        </View>
      </Page>

      {/* ── 01 EXECUTIVE SUMMARY ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="01" title="Executive Summary" />

        {s1 ? (
          <>
            {s1.risk_indicator && <RiskBadge indicator={s1.risk_indicator} />}
            <BodyText>{s1.overall_assessment || s1.narrative || ''}</BodyText>

            {s1.key_findings?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Key Findings</SubHeading>
                <Findings items={s1.key_findings} />
              </>
            )}

            {s1.immediate_actions?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Immediate Actions Required</SubHeading>
                {s1.immediate_actions.map((a: string, i: number) => (
                  <View key={i} style={styles.finding}>
                    <Text style={[styles.findingBullet, { color: '#C0392B' }]}>!</Text>
                    <Text style={styles.findingText}>{a}</Text>
                  </View>
                ))}
              </>
            )}
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>

      {/* ── 02 PORTFOLIO COMPOSITION ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="02" title="Portfolio Composition" />

        {s2 ? (
          <>
            <BodyText>{s2.narrative || ''}</BodyText>

            {s2.concentration_assessment && (
              <>
                <View style={styles.divider} />
                <SubHeading>Concentration Assessment</SubHeading>
                <BodyText>{s2.concentration_assessment}</BodyText>
              </>
            )}

            {s2.key_exposures?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Key Exposures</SubHeading>
                <Findings items={s2.key_exposures} />
              </>
            )}

            {s2.diversification_score && (
              <View style={{ marginTop: 10 }}>
                <Text style={styles.bodySmall}>
                  Diversification Score: {s2.diversification_score}
                  {s2.top_positions_commentary ? `  ·  ${s2.top_positions_commentary}` : ''}
                </Text>
              </View>
            )}
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>

      {/* ── 03 RISK SCORECARD ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="03" title="Risk Scorecard" />

        {s3 ? (
          <>
            <BodyText>{s3.narrative || ''}</BodyText>

            <View style={styles.metricGrid}>
              {s3.var_interpretation && (
                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>Value at Risk</Text>
                  <Text style={styles.metricSub}>{s3.var_interpretation}</Text>
                </View>
              )}
              {s3.volatility_assessment && (
                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>Volatility</Text>
                  <Text style={styles.metricSub}>{s3.volatility_assessment}</Text>
                </View>
              )}
              {s3.sharpe_assessment && (
                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>Risk-Adjusted Returns</Text>
                  <Text style={styles.metricSub}>{s3.sharpe_assessment}</Text>
                </View>
              )}
              {s3.trend_assessment && (
                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>Trend</Text>
                  <Text style={styles.metricSub}>{s3.trend_assessment}</Text>
                </View>
              )}
            </View>
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>

      {/* ── 04 COUNTERPARTY ANALYSIS ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="04" title="Counterparty Analysis" />

        {s4 ? (
          <>
            <BodyText>{s4.narrative || ''}</BodyText>

            {s4.custodian_concentration_risk && (
              <>
                <View style={styles.divider} />
                <SubHeading>Custodian Concentration</SubHeading>
                <BodyText>{s4.custodian_concentration_risk}</BodyText>
              </>
            )}

            {s4.highlighted_concerns?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Highlighted Concerns</SubHeading>
                {s4.highlighted_concerns.map((c: string, i: number) => (
                  <View key={i} style={styles.finding}>
                    <Text style={[styles.findingBullet, { color: '#C0392B' }]}>!</Text>
                    <Text style={styles.findingText}>{c}</Text>
                  </View>
                ))}
              </>
            )}

            {s4.watchlist?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Watchlist</SubHeading>
                <View style={styles.tagRow}>
                  {s4.watchlist.map((w: string, i: number) => (
                    <View key={i} style={styles.tag}>
                      <Text style={styles.tagText}>{w}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}

            {s4.overall_counterparty_assessment && (
              <View style={{ marginTop: 12 }}>
                <Text style={styles.bodySmall}>
                  Overall Counterparty Risk Assessment: {s4.overall_counterparty_assessment}
                </Text>
              </View>
            )}
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>

      {/* ── 05 STRESS TEST RESULTS ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="05" title="Stress Test Results" />

        {s5 ? (
          <>
            <BodyText>{s5.narrative || ''}</BodyText>

            <View style={styles.metricGrid}>
              {s5.worst_scenario && (
                <View style={[styles.metricCard, { backgroundColor: '#FEE2E2', width: '47%' }]}>
                  <Text style={[styles.metricLabel, { color: '#991B1B' }]}>Worst Scenario</Text>
                  <Text style={[styles.metricSub, { color: '#7F1D1D' }]}>{s5.worst_scenario}</Text>
                </View>
              )}
              {s5.resilience_assessment && (
                <View style={[styles.metricCard, { width: '47%' }]}>
                  <Text style={styles.metricLabel}>Resilience</Text>
                  <Text style={styles.metricSub}>{s5.resilience_assessment}</Text>
                </View>
              )}
            </View>

            {s5.tail_risk_commentary && (
              <>
                <View style={styles.divider} />
                <SubHeading>Tail Risk Commentary</SubHeading>
                <BodyText>{s5.tail_risk_commentary}</BodyText>
              </>
            )}
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>

      {/* ── 06 RECOMMENDATIONS ── */}
      <Page size="A4" style={styles.page}>
        <SectionTitle num="06" title="Recommendations" />

        {s6 ? (
          <>
            {s6.immediate?.length > 0 && (
              <>
                <SubHeading>Immediate Actions</SubHeading>
                {s6.immediate.map((a: any, i: number) => <ActionCard key={i} action={a} />)}
              </>
            )}

            {s6.short_term?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Short-Term Actions</SubHeading>
                {s6.short_term.map((a: any, i: number) => <ActionCard key={i} action={a} />)}
              </>
            )}

            {s6.monitoring?.length > 0 && (
              <>
                <View style={styles.divider} />
                <SubHeading>Ongoing Monitoring</SubHeading>
                {s6.monitoring.map((m: any, i: number) => (
                  <View key={i} style={styles.finding}>
                    <Text style={styles.findingBullet}>·</Text>
                    <Text style={styles.findingText}>
                      {m.item}{m.threshold ? ` — Alert if: ${m.threshold}` : ''}
                    </Text>
                  </View>
                ))}
              </>
            )}

            {s6.disclaimer && (
              <>
                <View style={styles.divider} />
                <Text style={styles.disclaimer}>{s6.disclaimer}</Text>
              </>
            )}
          </>
        ) : (
          <BodyText>This section was not generated.</BodyText>
        )}

        <PageFooter reportRef={report.report_ref} period={report.report_period} />
      </Page>
    </Document>
  )
}
