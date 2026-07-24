{{/* Chart name (overridable). */}}
{{- define "tg-notes.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully qualified app name. */}}
{{- define "tg-notes.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "tg-notes.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "tg-notes.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tg-notes.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "tg-notes.labels" -}}
helm.sh/chart: {{ include "tg-notes.chart" . }}
{{ include "tg-notes.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "tg-notes.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "tg-notes.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Fully-qualified image reference; empty tag falls back to appVersion. */}}
{{- define "tg-notes.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}

{{/* Voice model PVC name (created here unless an existingClaim is given). */}}
{{- define "tg-notes.voiceClaimName" -}}
{{- if .Values.voiceModel.existingClaim -}}
{{- .Values.voiceModel.existingClaim -}}
{{- else -}}
{{- printf "%s-models" (include "tg-notes.fullname" .) -}}
{{- end -}}
{{- end -}}
