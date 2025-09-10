{{/*
Helpers estándar para nombres y labels del chart
*/}}

{{- define "news-semantic-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "news-semantic-api.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "news-semantic-api.name" . -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end }}

{{- define "news-semantic-api.labels" -}}
app.kubernetes.io/name: {{ include "news-semantic-api.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | default .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "news-semantic-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "news-semantic-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
