---
name: PayMender
description: Light payment-recovery operations interface
colors:
  bg: "#f6f7fb"
  surface: "#ffffff"
  surface-2: "#f0f2f8"
  border: "#e2e5ed"
  border-bright: "#c6cbd8"
  muted: "#626b7e"
  text: "#202637"
  primary: "#5145cd"
  primary-hover: "#4035ae"
  primary-tint: "#f0effc"
  success: "#16734d"
  red: "#b83c37"
  amber-text: "#855709"
  amber-border: "#ead9b6"
  amber-bg: "#fff9ed"
  amber-dot: "#a47112"
  success-border: "#b8dccb"
  success-bg: "#f0faf5"
  red-border: "#f0cecb"
  red-bg: "#fdf3f2"
typography:
  headline:
    fontFamily: '"Segoe UI Variable", "Aptos", ui-sans-serif, system-ui, sans-serif'
    fontSize: "clamp(25px, 2.4vw, 32px)"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.9px"
  body:
    fontFamily: '"Segoe UI Variable", "Aptos", ui-sans-serif, system-ui, sans-serif'
    fontSize: "14px"
    lineHeight: 1.55
  label:
    fontFamily: '"Segoe UI Variable", "Aptos", ui-sans-serif, system-ui, sans-serif'
    fontSize: "12px"
  metric:
    fontFamily: '"Segoe UI Variable", "Aptos", ui-sans-serif, system-ui, sans-serif'
    fontSize: "27px"
    fontWeight: 620
    letterSpacing: "-.8px"
rounded:
  tag: "5px"
  control: "7px"
  field: "8px"
  navigation: "9px"
  metric: "10px"
  panel: "12px"
  access: "16px"
  pill: "99px"
spacing:
  compact: "8px"
  small: "12px"
  medium: "16px"
  panel: "20px"
  section: "24px"
  page: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.primary}"
    padding: "8px 0"
  operator-field:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "0 12px"
    width: "100%"
  navigation-active:
    backgroundColor: "{colors.primary-tint}"
    textColor: "{colors.primary}"
    rounded: "{rounded.navigation}"
    padding: "10px 12px"
  status-amber:
    backgroundColor: "{colors.amber-bg}"
    textColor: "{colors.amber-text}"
    rounded: "{rounded.tag}"
    padding: "4px 7px"
  metric-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.metric}"
    padding: "18px 20px"
---

# Design System: PayMender

## Overview

PayMender uses a light payment-operations interface: white surfaces, a cool neutral canvas, indigo actions and compact, labelled case information. The hierarchy supports scanning a portfolio, inspecting evidence and making an explicit decision.

This documents the implementation in `frontend/src/styles.css`, `workflow.css`, `App.tsx`, `PortfolioSnapshot.tsx` and `RecoveryWorkflow.tsx`. Public Churnkey, Churn Buster and Baremetrics interface references informed the refresh; this is an adaptation with PayMender's identity, not an exact replica or an approved visual comp. Reference provenance is recorded in `docs/frontend-reference-refresh.md`.

Key characteristics: restrained color, visible separators, contextual metric labels, text-backed status graphics and labelled navigation at every supported size. Tokens above are normative; component-specific exceptions and behavior follow below. No external image or font assets are required.

## Colors

Indigo is the primary action and selection color. Its darker hover value indicates interaction; its pale tint distinguishes active navigation, selected cases and policy recommendations. Success green, warning amber and error red accompany explicit state labels.

The neutral palette separates page background, white panels, inset surfaces, borders, body text and secondary text. Use the existing muted token for explanatory copy and the operator-token placeholder; the latter explicitly uses full opacity.

The Payment status graphic uses its own categorical values from `PortfolioSnapshot.tsx`: halted `#ba852a`, pending `#6860c9`, active `#557ab5`, authenticated `#45838b`, charged `#27936b`, cancelled/fallback `#8991a3`, completed `#b2b8c6`. These identify subscription categories, not approval progress or attributed recovery. Every segment has a text label and count.

## Typography

Use the local system sans-serif stack in the tokens. Page introductions use the headline and body roles, with introductory text capped at 68 characters per line. Section labels are generally 14px; supporting labels range from 11–12px. Metric values use the metric role and tabular numerals, as do amounts, score values and tables.

Workflow explanations use 15px text at 1.75 line height and a 70-character maximum line length, increasing to 16px on phones. Workflow titles use 27px, weight 600, line height 1.25; phone titles become 24px. Uppercase styling is limited to compact identity and metadata labels in the existing interface.

## Layout

The desktop shell pairs a fixed 224px sidebar with a flexible main area. The top bar is sticky and 66px high. Content has a 1680px maximum width and page padding of 28px 28px 48px. Four portfolio metrics share one bordered strip; the review workspace pairs a 300px queue with the flexible inspector, separated by 20px. The queue sticks 82px below the viewport top and scrolls internally.

At widths up to 1100px, the labelled sidebar narrows to 76px, page gutters become 22px, the queue becomes 275px and inspector panels stack. Case progress changes from four columns to two. The workflow retains two columns with an 18px gap.

At widths up to 760px, navigation becomes a fixed 76px bottom bar and content reserves that space. Page padding becomes 24px 14px 38px. Metrics become a two-by-two strip; queue and inspector stack. The queue is capped at 380px, its list at 320px. Workflow content becomes one column; stage controls reduce from 68px to 52px minimum height. Search and queue selects use 16px text. Toasts sit above navigation at 90px from the bottom. The body supports a 320px minimum width.

## Elevation & Depth

Panels rely on white and inset surfaces with thin borders, without general card shadows. The centered access card uses `0 12px 48px rgb(32 38 55 / 6%)`; the floating toast uses `0 8px 32px rgb(32 38 55 / 12%)`. Sticky navigation and the top bar remain opaque. Depth values are also recorded in the sidecar.

## Shapes

Controls and panels use the rounded tokens above, with one-pixel borders. The queue is a contiguous list of square-edged rows within a rounded container; selection adds a 3px indigo left edge. Avatars and progress markers are circular. The Payment status track is 12px high with a 4px radius and 3px gaps; legend swatches are 8px squares with 2px corners.

## Components

- Buttons: primary and ghost controls have a 44px minimum height, 13px text at weight 600, and the tokenized padding. Primary hover darkens; ghost hover uses the inset surface. Text buttons use an underline on hover. Existing compact link actions are a 34px exception. Disabled primary/ghost controls use opacity 0.6 and a wait cursor.
- Inputs: the operator field has a 44px minimum height, brighter neutral border, inset surface and explicit muted placeholder at opacity 1. Focus changes its border to indigo. Search/select controls use a 6px radius, 9px padding and the page background.
- Navigation: sidebar selection uses a pale indigo fill with indigo text. Inspector switches use an indigo bottom border and `aria-pressed`; workflow stages pair icons with full labels and a selected tint. Keep those labels visible in compact navigation.
- Status tags: compact text, a matching dot and a light semantic background. State meaning comes from the label as well as color. Neutral is the default; amber, green and red are explicit variants.
- Metric cards: compact label, tabular value and contextual note. The command-center strip removes individual rounding and uses internal dividers. Predicted recoverable has an indigo tint; its estimate label remains visible.
- Review patterns: case progress separates context, safety review, decision and outcome. Decision, model evidence and message previews have distinct switches. A created link remains labelled payment-unconfirmed until matching recovery evidence arrives.
- Status snapshot: categorical segments reflect actual current case counts. A text legend provides every count, and an empty portfolio shows an explicit empty state.

Buttons transition color, background, border and transform over 180ms with `ease`, and press down 1px when enabled. Loading icons spin over 800ms linearly. Keyboard focus uses a 2px indigo outline offset by 3px. Reduced-motion preference changes animation/transition duration to 0.01ms, limits animation to one iteration and disables smooth scrolling.

## Do's and Don'ts

- Do use the existing neutral and indigo tokens for surfaces, actions and selection.
- Do retain text labels and counts alongside status colors.
- Do preserve visible focus, responsive navigation labels and reduced-motion handling.
- Do keep estimates, synthetic results and confirmed payment evidence visibly distinct.
- Don't turn a created payment link or a charged subscription into an attributed recovery claim.
- Don't copy competitor branding, proprietary assets or sample performance figures.
- Don't present this extracted system as a user-approved visual comp or a permanent preference beyond this project.
