import { useEffect, useMemo, useState } from 'react';

const apiBase = '/api/v1';
const legacyStorageKey = 'clinica-pechychon-superuser-token';

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();

  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }

  if (!response.ok) {
    const message = typeof data === 'string' ? data : data?.detail || response.statusText;
    throw new Error(message || 'No se pudo completar la solicitud.');
  }

  return data;
}

function formatGender(value) {
  const map = {
    male: 'Masculino',
    female: 'Femenino',
    other: 'Otro',
    unknown: 'No reportado',
  };
  return map[value] || value || 'No reportado';
}

function getHumanName(resource) {
  const firstName = resource?.name?.[0];
  if (!firstName) {
    return 'Paciente sin nombre';
  }

  const given = Array.isArray(firstName.given) ? firstName.given.join(' ') : '';
  const family = firstName.family || '';
  return [given, family].filter(Boolean).join(' ') || 'Paciente sin nombre';
}

function getPrimaryIdentifier(resource) {
  const identifier = resource?.identifier?.[0];
  if (!identifier) {
    return 'Sin identificador';
  }

  const type = identifier?.type?.coding?.[0]?.code;
  const value = identifier?.value;

  if (type && value) {
    return `${type}|${value}`;
  }

  return value || 'Sin identificador';
}

function getHeartPathology(resource) {
  const extensions = Array.isArray(resource?.extension) ? resource.extension : [];
  const pathologyExtension = extensions.find(
    (item) => item?.url === 'https://pechychon.local/fhir/StructureDefinition/heart-disease-pathology'
  );
  return pathologyExtension?.valueString || 'Sin patología registrada';
}

function extractPatients(bundle) {
  const entries = Array.isArray(bundle?.entry) ? bundle.entry : [];

  return entries.map((entry, index) => {
    const resource = entry?.resource || {};
    return {
      key: resource.id || entry?.fullUrl || `patient-${index}`,
      id: resource.id || 'Sin ID',
      name: getHumanName(resource),
      identifier: getPrimaryIdentifier(resource),
      gender: resource.gender || 'unknown',
      birthDate: resource.birthDate || 'Sin fecha',
      pathology: getHeartPathology(resource),
      active: resource.active ?? true,
      raw: resource,
    };
  });
}

function summarizeObservation(bundle) {
  const entries = Array.isArray(bundle?.entry) ? bundle.entry : [];

  return entries.slice(0, 8).map((entry, index) => {
    const resource = entry?.resource || {};
    const coding = resource?.code?.coding?.[0];
    const label = coding?.display || coding?.code || `Observación ${index + 1}`;
    const quantityValue = resource?.valueQuantity?.value;
    const quantityUnit = resource?.valueQuantity?.unit || '';
    const value = typeof quantityValue === 'number' || typeof quantityValue === 'string'
      ? `${quantityValue} ${quantityUnit}`.trim()
      : 'Sin valor numérico';

    return {
      id: resource?.id || `obs-${index}`,
      label,
      value,
      date: resource?.effectiveDateTime || 'Sin fecha',
      status: resource?.status || 'unknown',
    };
  });
}

function normalizeErrorMessage(error, fallback) {
  const text = String(error?.message || '').toLowerCase();
  if (
    text.includes('failed to fetch') ||
    text.includes('network') ||
    text.includes('cannot') ||
    text.includes('503') ||
    text.includes('solicitud') ||
    text.includes('500')
  ) {
    return fallback;
  }
  return error?.message || fallback;
}

function toCsvValue(value) {
  const text = String(value ?? '');
  if (text.includes(',') || text.includes('"') || text.includes('\n')) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function App() {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState('Ingrese sus credenciales para continuar.');
  const [email, setEmail] = useState('medico@pechychon.com');
  const [password, setPassword] = useState('SuperPass2026');
  const [licenseNumber, setLicenseNumber] = useState('MED123456');
  const [activeTab, setActiveTab] = useState('inicio');

  const [identifier, setIdentifier] = useState('CC|1234567890');
  const [patients, setPatients] = useState([]);
  const [searchMessage, setSearchMessage] = useState('Aún no hay búsquedas realizadas.');
  const [selectedPatient, setSelectedPatient] = useState(null);

  const [newPatient, setNewPatient] = useState({
    identifierType: 'CC',
    identifierValue: '1234567890',
    family: 'Pérez',
    given: 'Laura',
    gender: 'female',
    birthDate: '1990-06-12',
  });
  const [createMessage, setCreateMessage] = useState('Complete el formulario para registrar un nuevo paciente.');
  const [importingDataset, setImportingDataset] = useState(false);
  const [importMessage, setImportMessage] = useState('Puede cargar pacientes desde el dataset UCI Heart Disease.');
  const [datasetReady, setDatasetReady] = useState(false);
  const [patientSearch, setPatientSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [pathologyFilter, setPathologyFilter] = useState('all');
  const [pageSize, setPageSize] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedPatientId, setExpandedPatientId] = useState('');
  const [editingPatientId, setEditingPatientId] = useState('');
  const [procedureComment, setProcedureComment] = useState('');
  const [actionLogs, setActionLogs] = useState([]);
  const [pendingConfirm, setPendingConfirm] = useState(null);
  const [toasts, setToasts] = useState([]);

  const [observationPatientId, setObservationPatientId] = useState('1');
  const [loincCode, setLoincCode] = useState('');
  const [observationCount, setObservationCount] = useState('10');
  const [observationMessage, setObservationMessage] = useState('Consulte las observaciones clínicas del paciente.');
  const [observationData, setObservationData] = useState(null);
  const [newObservationCode, setNewObservationCode] = useState('8867-4');
  const [newObservationValue, setNewObservationValue] = useState('72');
  const [newObservationUnit, setNewObservationUnit] = useState('lat/min');
  const [observationComment, setObservationComment] = useState('');

  const [inferencePatientId, setInferencePatientId] = useState('');
  const [modelType, setModelType] = useState('tabular');
  const [modelName, setModelName] = useState('diabetes');
  const [inferenceMessage, setInferenceMessage] = useState('Ejecute una evaluación para ver el resultado del apoyo clínico.');
  const [inferenceData, setInferenceData] = useState(null);
  const [alejoMessage, setAlejoMessage] = useState('Alejo te sugiere seleccionar un paciente y ejecutar el análisis tabular de riesgo cardíaco.');

  const [deleteReason, setDeleteReason] = useState('Paciente trasladado.');
  const [deleteIcd10, setDeleteIcd10] = useState('I25.1');
  const [deleteMessage, setDeleteMessage] = useState('');

  const [agentPatientId, setAgentPatientId] = useState('1');
  const [agentQuestion, setAgentQuestion] = useState('¿Cuál es el riesgo cardíaco de este paciente y qué conducta clínica inicial recomiendas?');
  const [agentModelType, setAgentModelType] = useState('tabular');
  const [agentStrategy, setAgentStrategy] = useState('hybrid');
  const [agentSessionId, setAgentSessionId] = useState('');
  const [agentMessage, setAgentMessage] = useState('Haga una consulta para obtener apoyo clínico contextual.');
  const [agentData, setAgentData] = useState(null);

  useEffect(() => {
    localStorage.removeItem(legacyStorageKey);
  }, []);

  useEffect(() => {
    if (token) {
      setStatus('Sesión activa. Bienvenido al portal clínico.');
    } else {
      setStatus('Ingrese sus credenciales para continuar.');
    }
  }, [token]);

  const isAuthenticated = Boolean(token);

  const authHeaders = useMemo(() => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }), [token]);

  const dashboard = useMemo(() => {
    const active = patients.filter((item) => item.active).length;
    const observationRows = summarizeObservation(observationData);
    const probabilityValue = typeof inferenceData?.probability === 'number'
      ? `${Math.round(inferenceData.probability * 100)}%`
      : 'No disponible';

    return {
      totalPatients: patients.length,
      activePatients: active,
      selectedPatient: selectedPatient?.name || 'Sin paciente seleccionado',
      observationCount: observationRows.length,
      prediction: inferenceData?.prediction || 'Sin predicción reciente',
      probability: probabilityValue,
      observationRows,
    };
  }, [patients, selectedPatient, observationData, inferenceData]);

  const pathologyOptions = useMemo(() => {
    const set = new Set();
    patients.forEach((patient) => {
      if (patient?.pathology) {
        set.add(patient.pathology);
      }
    });
    return ['all', ...Array.from(set)];
  }, [patients]);

  const filteredPatients = useMemo(() => {
    return patients.filter((patient) => {
      const query = patientSearch.trim().toLowerCase();
      const textOk = !query
        || patient.name.toLowerCase().includes(query)
        || patient.identifier.toLowerCase().includes(query)
        || (patient.pathology || '').toLowerCase().includes(query);
      const genderOk = genderFilter === 'all' || patient.gender === genderFilter;
      const statusOk = statusFilter === 'all'
        || (statusFilter === 'active' && patient.active)
        || (statusFilter === 'inactive' && !patient.active);
      const pathologyOk = pathologyFilter === 'all' || patient.pathology === pathologyFilter;
      return textOk && genderOk && statusOk && pathologyOk;
    });
  }, [patients, patientSearch, genderFilter, statusFilter, pathologyFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredPatients.length / pageSize));

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const paginatedPatients = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredPatients.slice(start, start + pageSize);
  }, [filteredPatients, currentPage, pageSize]);

  const patientOptions = useMemo(() => {
    return patients.map((patient) => ({
      value: String(patient.id),
      label: `${patient.name} (${patient.identifier})`,
    }));
  }, [patients]);

  useEffect(() => {
    if (patients.length > 0 && !selectedPatient) {
      setSelectedPatient(patients[0]);
    }
  }, [patients, selectedPatient]);

  useEffect(() => {
    if (!selectedPatient?.id) {
      return;
    }

    const selectedId = String(selectedPatient.id);
    setObservationPatientId(selectedId);
    setInferencePatientId(selectedId);
    setAgentPatientId(selectedId);
  }, [selectedPatient?.id]);

  const buildPatientPayload = () => {
    const givenNames = newPatient.given
      .split(' ')
      .map((part) => part.trim())
      .filter(Boolean);

    return {
      resourceType: 'Patient',
      identifier: [
        {
          use: 'official',
          type: {
            coding: [{ system: 'http://terminology.hl7.org/CodeSystem/v2-0203', code: newPatient.identifierType || 'CC' }],
          },
          value: newPatient.identifierValue,
        },
      ],
      name: [{ family: newPatient.family, given: givenNames }],
      gender: newPatient.gender,
      birthDate: newPatient.birthDate,
    };
  };

  const clearSession = () => {
    setToken('');
    setStatus('Sesión cerrada.');
    setPatients([]);
    setDatasetReady(false);
    setPatientSearch('');
    setGenderFilter('all');
    setStatusFilter('all');
    setPathologyFilter('all');
    setPageSize(25);
    setCurrentPage(1);
    setExpandedPatientId('');
    setEditingPatientId('');
    setProcedureComment('');
    setActionLogs([]);
    setPendingConfirm(null);
    setSelectedPatient(null);
    setSearchMessage('Aún no hay búsquedas realizadas.');
    setCreateMessage('Complete el formulario para registrar un nuevo paciente.');
    setObservationMessage('Consulte las observaciones clínicas del paciente.');
    setObservationData(null);
    setObservationComment('');
    setInferencePatientId('');
    setInferenceMessage('Ejecute una evaluación para ver el resultado del apoyo clínico.');
    setInferenceData(null);
    setDeleteMessage('');
    setAgentMessage('Haga una consulta para obtener apoyo clínico contextual.');
    setAgentData(null);
    setToasts([]);
  };

  const pushToast = (type, message) => {
    if (!message) {
      return;
    }
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((current) => [...current, { id, type, message }].slice(-4));
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 4200);
  };

  const dismissToast = (id) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  };

  const mapProcedureLog = (item) => ({
    id: item.id || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    action: item.action || 'Procedimiento',
    patientName: item.patient_name || item.patientName || 'Sin paciente',
    patientIdentifier: item.patient_identifier || item.patientIdentifier || 'Sin identificador',
    comment: item.comment || '',
    timestamp: item.timestamp
      ? new Date(item.timestamp).toLocaleString('es-CO')
      : new Date().toLocaleString('es-CO'),
  });

  const loadProcedureLogs = async (accessToken = token) => {
    if (!accessToken) {
      return;
    }
    try {
      const data = await fetchJson(`${apiBase}/superuser/procedure-logs?limit=50`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const rows = Array.isArray(data) ? data.map(mapProcedureLog) : [];
      setActionLogs(rows);
    } catch {
      setActionLogs([]);
    }
  };

  const addActionLog = async (action, patient, comment) => {
    const payload = {
      action,
      patient_id: String(patient?.id || ''),
      patient_name: patient?.name || 'Sin paciente',
      patient_identifier: patient?.identifier || 'Sin identificador',
      comment,
    };

    try {
      const created = await fetchJson(`${apiBase}/superuser/procedure-logs`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(payload),
      });
      setActionLogs((current) => [mapProcedureLog(created), ...current].slice(0, 50));
    } catch {
      const fallback = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        action,
        patientName: patient?.name || 'Sin paciente',
        patientIdentifier: patient?.identifier || 'Sin identificador',
        comment,
        timestamp: new Date().toLocaleString('es-CO'),
      };
      setActionLogs((current) => [fallback, ...current].slice(0, 50));
      pushToast('warning', 'No se pudo persistir la bitácora en backend. Se guardó localmente.');
    }
  };

  const requireProcedureComment = () => {
    const comment = procedureComment.trim();
    if (!comment) {
      setDeleteMessage('Debe escribir un comentario explicando el procedimiento.');
      pushToast('warning', 'Debe escribir un comentario del procedimiento.');
      return null;
    }
    return comment;
  };

  const openPatientMenu = (patient) => {
    setSelectedPatient(patient);
    setExpandedPatientId(String(patient.id));
    setEditingPatientId('');
  };

  const configureWithAlejo = () => {
    setModelType('tabular');
    setModelName('cardiac-risk-v1');
    setAlejoMessage('Alejo configuró el análisis de riesgo cardíaco tabular. Ahora pulsa "Evaluar paciente".');
  };

  const getPatientById = (id) => {
    const wanted = String(id || '').trim();
    if (!wanted) {
      return null;
    }
    return patients.find((patient) => String(patient.id) === wanted) || null;
  };

  const composeLocalAssistantGuidance = (patient, question) => {
    const pathology = patient?.pathology || 'patología no especificada';
    const prediction = inferenceData?.prediction || 'sin predicción previa';
    const probability = typeof inferenceData?.probability === 'number'
      ? `${Math.round(inferenceData.probability * 100)}%`
      : 'no disponible';

    return `Riesgo cardiovascular orientativo para ${patient?.name || 'el paciente'}: ${pathology}. Última inferencia: ${prediction} (confianza ${probability}). Pregunta recibida: ${question}. Recomendación inicial: confirmar signos de alarma, revisar factores de riesgo, validar con criterios clínicos y definir si requiere prioridad en cardiología.`;
  };

  const applyDeactivatePatient = async (patient, comment) => {
    const selectedId = String(patient.id);

    if (!selectedId.startsWith('dataset-row-')) {
      await fetchJson(`${apiBase}/superuser/patients/${encodeURIComponent(selectedId)}`, {
        method: 'DELETE',
        headers: authHeaders,
        body: JSON.stringify({ reason: comment, icd10_code: deleteIcd10 }),
      });
    }

    setPatients((current) => current.map((item) => (
      String(item.id) === selectedId ? { ...item, active: false } : item
    )));
    setSelectedPatient((current) => (current ? { ...current, active: false } : current));
    await addActionLog('Paciente inactivado', patient, comment);
    setDeleteMessage('Paciente inactivado correctamente (soft delete).');
  };

  const applyActivatePatient = async (patient, comment) => {
    const selectedId = String(patient.id);
    setPatients((current) => current.map((item) => (
      String(item.id) === selectedId ? { ...item, active: true } : item
    )));
    setSelectedPatient((current) => (current ? { ...current, active: true } : current));
    await addActionLog('Paciente activado', patient, comment);
    setDeleteMessage('Paciente activado localmente en el portal.');
  };

  const applyRemovePatient = async (patient, comment) => {
    const selectedId = String(patient.id);
    if (!selectedId.startsWith('dataset-row-')) {
      await fetchJson(`${apiBase}/superuser/patients/${encodeURIComponent(selectedId)}`, {
        method: 'DELETE',
        headers: authHeaders,
        body: JSON.stringify({ reason: comment, icd10_code: deleteIcd10 }),
      });
    }

    setPatients((current) => current.filter((item) => String(item.id) !== selectedId));
    setSelectedPatient((current) => (String(current?.id || '') === selectedId ? null : current));
    await addActionLog('Paciente eliminado de la vista', patient, comment);
    setDeleteMessage('Paciente eliminado de la tabla actual.');
  };

  const askConfirmAction = (action, patient) => {
    const comment = requireProcedureComment();
    if (!comment) {
      return;
    }
    const labels = {
      deactivate: '¿Confirmar inactivación del paciente?',
      activate: '¿Confirmar activación del paciente?',
      remove: '¿Confirmar eliminación del paciente de esta vista?',
    };
    setPendingConfirm({ action, patientId: String(patient.id), message: labels[action], comment });
  };

  const executeConfirmedAction = async () => {
    if (!pendingConfirm) {
      return;
    }
    const patient = getPatientById(pendingConfirm.patientId);
    if (!patient) {
      setPendingConfirm(null);
      return;
    }

    try {
      if (pendingConfirm.action === 'deactivate') {
        await applyDeactivatePatient(patient, pendingConfirm.comment);
        pushToast('success', 'Paciente inactivado correctamente.');
      }
      if (pendingConfirm.action === 'activate') {
        await applyActivatePatient(patient, pendingConfirm.comment);
        pushToast('success', 'Paciente activado correctamente.');
      }
      if (pendingConfirm.action === 'remove') {
        await applyRemovePatient(patient, pendingConfirm.comment);
        pushToast('success', 'Paciente eliminado de la tabla actual.');
      }
      setExpandedPatientId('');
      setEditingPatientId('');
      setProcedureComment('');
    } catch (error) {
      setDeleteMessage(error.message || 'No se pudo completar la acción sobre el paciente.');
      pushToast('error', error.message || 'No se pudo completar la acción sobre el paciente.');
    } finally {
      setPendingConfirm(null);
    }
  };

  const createObservation = async (event) => {
    event.preventDefault();
    const comment = observationComment.trim();
    if (!comment) {
      setObservationMessage('Debe escribir un comentario para registrar la observación.');
      pushToast('warning', 'Debe escribir un comentario para guardar la observación.');
      return;
    }

    const selected = getPatientById(observationPatientId) || selectedPatient;
    if (!selected?.id) {
      setObservationMessage('Seleccione un paciente para crear observación.');
      return;
    }

    const entryDate = new Date().toISOString();
    const syntheticEntry = {
      resourceType: 'Observation',
      id: `obs-local-${Date.now()}`,
      status: 'final',
      code: {
        coding: [{ system: 'http://loinc.org', code: newObservationCode || '8867-4', display: 'Observación clínica' }],
      },
      valueQuantity: {
        value: Number(newObservationValue) || newObservationValue,
        unit: newObservationUnit || 'unidad',
      },
      effectiveDateTime: entryDate,
      note: [{ text: comment }],
      subject: { reference: `Patient/${selected.id}` },
    };

    try {
      if (!String(selected.id).startsWith('dataset-row-')) {
        await fetchJson(`${apiBase}/superuser/patients/${encodeURIComponent(String(selected.id))}/observations`, {
          method: 'POST',
          headers: authHeaders,
          body: JSON.stringify(syntheticEntry),
        });
      }

      const previousEntries = Array.isArray(observationData?.entry) ? observationData.entry : [];
      setObservationData({
        resourceType: 'Bundle',
        type: 'searchset',
        total: previousEntries.length + 1,
        entry: [{ resource: syntheticEntry }, ...previousEntries],
      });
      setObservationMessage('Observación registrada correctamente.');
      await addActionLog('Observación registrada', selected, comment);
      setObservationComment('');
      setExpandedPatientId('');
      setEditingPatientId('');
      pushToast('success', 'Observación registrada y bitácora actualizada.');
    } catch (error) {
      setObservationMessage(error.message || 'No se pudo registrar la observación.');
      pushToast('error', error.message || 'No se pudo registrar la observación.');
    }
  };

  const login = async (event) => {
    event.preventDefault();
    setStatus('Validando acceso...');

    try {
      const data = await fetchJson(`${apiBase}/auth/superuser/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, license_number: licenseNumber }),
      });

      if (data.access_token) {
        setToken(data.access_token);
        setActiveTab('inicio');
        pushToast('success', 'Sesión iniciada correctamente.');
        loadProcedureLogs(data.access_token);
        if (!datasetReady) {
          importHeartDataset({ accessToken: data.access_token, silent: true, limit: 30 });
        }
      } else {
        setStatus('No se recibió un token válido.');
        pushToast('error', 'No se recibió un token válido.');
      }
    } catch (error) {
      setStatus(error.message || 'No fue posible iniciar sesión.');
      pushToast('error', error.message || 'No fue posible iniciar sesión.');
    }
  };

  const searchPatients = async (event) => {
    event.preventDefault();

    try {
      const data = await fetchJson(`${apiBase}/superuser/patients?identifier=${encodeURIComponent(identifier)}`, {
        headers: authHeaders,
      });

      const rows = extractPatients(data);
      setPatients(rows);
      setSelectedPatient(rows[0] || null);
      setSearchMessage(`Se encontraron ${rows.length} paciente(s).`);
    } catch (error) {
      setPatients([]);
      setSelectedPatient(null);
      setSearchMessage(error.message || 'No se pudo consultar pacientes.');
    }
  };

  const createPatient = async (event) => {
    event.preventDefault();

    try {
      const payload = buildPatientPayload();
      const data = await fetchJson(`${apiBase}/superuser/patients`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(payload),
      });

      const created = {
        key: data.id || data.fullUrl || `patient-${Date.now()}`,
        id: data.id || 'Sin ID',
        name: getHumanName(data),
        identifier: getPrimaryIdentifier(data),
        gender: data.gender || 'unknown',
        birthDate: data.birthDate || 'Sin fecha',
        pathology: getHeartPathology(data),
        active: data.active ?? true,
        raw: data,
      };

      setPatients((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setSelectedPatient(created);
      setCreateMessage('Paciente registrado correctamente.');
    } catch (error) {
      setCreateMessage(error.message || 'No se pudo registrar el paciente.');
    }
  };

  const importHeartDataset = async ({ accessToken = token, silent = false, limit = 303 } = {}) => {
    setImportingDataset(true);
    if (!silent) {
      setImportMessage('Cargando lista de pacientes desde UCI Heart Disease...');
    }

    try {
      const data = await fetchJson(`${apiBase}/superuser/patients/import/heart-disease?limit=${encodeURIComponent(String(limit))}&offset=0`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
      });

      const datasetRows = Array.isArray(data?.patients) ? data.patients : [];
      const importedPatients = datasetRows
        .map((item, index) => ({
          key: item.id || `uci-row-${item.row ?? index}`,
          id: item.id || `dataset-row-${item.row ?? index}`,
          name: item.name || 'Paciente dataset',
          identifier: item.identifier || 'Sin identificador',
          gender: item.gender || 'unknown',
          birthDate: item.birthDate || 'Sin fecha',
          pathology: item.heart_pathology || 'Patología no reportada',
          active: true,
          raw: {
            resourceType: 'Patient',
            id: item.id || `dataset-row-${item.row ?? index}`,
            gender: item.gender || 'unknown',
            birthDate: item.birthDate || '1970-01-01',
            extension: [
              {
                url: 'https://pechychon.local/fhir/StructureDefinition/heart-disease-pathology',
                valueString: item.heart_pathology || 'Patología no reportada',
              },
            ],
            identifier: [
              {
                value: item.identifier?.split('|')[1] || item.identifier || 'SIN-ID',
                type: {
                  coding: [
                    {
                      code: item.identifier?.split('|')[0] || 'CC',
                    },
                  ],
                },
              },
            ],
            name: [
              {
                family: item.name?.split(' ').slice(-1).join(' ') || 'Dataset',
                given: item.name?.split(' ').slice(0, -1).filter(Boolean) || ['Paciente'],
              },
            ],
            active: true,
          },
        }));

      setPatients(importedPatients);
      setDatasetReady(true);
      setCurrentPage(1);

      if (importedPatients.length > 0) {
        setSelectedPatient(importedPatients[0]);
      } else {
        setSelectedPatient(null);
      }

      setSearchMessage(`Lista de dataset cargada: ${importedPatients.length} paciente(s).`);

      if (!silent) {
        setImportMessage(`Dataset aplicado: ${data?.created_count || 0} creados, ${data?.skipped_count || 0} existentes.`);
        pushToast('success', `Dataset aplicado: ${importedPatients.length} pacientes listos.`);
      }
    } catch (error) {
      setImportMessage(error.message || 'No se pudo cargar la lista del dataset UCI Heart Disease.');
      pushToast('error', error.message || 'No se pudo cargar la lista del dataset UCI Heart Disease.');
    } finally {
      setImportingDataset(false);
    }
  };

  const exportPatientsCsv = () => {
    if (filteredPatients.length === 0) {
      setImportMessage('No hay pacientes para exportar.');
      return;
    }

    const header = ['Nombre', 'Identificación', 'Género', 'Nacimiento', 'Patología cardíaca', 'Estado'];
    const rows = filteredPatients.map((patient) => ([
      patient.name,
      patient.identifier,
      formatGender(patient.gender),
      patient.birthDate,
      patient.pathology || 'Sin patología registrada',
      patient.active ? 'Activo' : 'Inactivo',
    ]));

    const csv = [header, ...rows]
      .map((row) => row.map((value) => toCsvValue(value)).join(','))
      .join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'pacientes_cardiologia_dataset.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  const fetchObservations = async (event) => {
    event.preventDefault();

    try {
      const params = new URLSearchParams({ _count: observationCount || '10' });
      if (loincCode.trim()) {
        params.set('loinc_code', loincCode.trim());
      }

      const data = await fetchJson(`${apiBase}/superuser/patients/${encodeURIComponent(observationPatientId)}/observations?${params.toString()}`, {
        headers: authHeaders,
      });

      setObservationData(data);
      const total = Array.isArray(data?.entry) ? data.entry.length : 0;
      setObservationMessage(`Se encontraron ${total} observación(es).`);
    } catch (error) {
      setObservationData(null);
      setObservationMessage(error.message || 'No se pudieron consultar observaciones.');
    }
  };

  const runInference = async (event) => {
    event.preventDefault();

    try {
      const patientForInference = getPatientById(inferencePatientId) || selectedPatient;

      const patientPayload = patientForInference?.raw || {
        resourceType: 'Patient',
        id: inferencePatientId || observationPatientId,
      };

      const data = await fetchJson(`${apiBase}/superuser/inference/${modelType}`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          patient_fhir: patientPayload,
          model: modelName,
        }),
      });

      setInferenceData(data);
      setInferenceMessage('Evaluación completada con éxito.');
    } catch (error) {
      setInferenceData(null);
      setInferenceMessage(error.message || 'No fue posible ejecutar la evaluación.');
    }
  };

  const queryAgent = async (event) => {
    event.preventDefault();

    const selectedForAssistant = getPatientById(agentPatientId) || selectedPatient;

    try {
      const payload = {
        patient_id: agentPatientId || selectedForAssistant?.id || '1',
        question: agentQuestion,
        model_type: agentModelType,
        rag_strategy: agentStrategy,
      };

      if (agentSessionId.trim()) {
        payload.session_id = agentSessionId.trim();
      }

      const data = await fetchJson('/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (typeof data?.session_id === 'string') {
        setAgentSessionId(data.session_id);
      }

      setAgentData(data);
      setAgentMessage('Consulta completada.');
    } catch (error) {
      const localResponse = composeLocalAssistantGuidance(selectedForAssistant, agentQuestion);
      setAgentData({
        answer: {
          prediction: localResponse,
          retrieved_contexts: [
            `Paciente: ${selectedForAssistant?.name || 'Sin selección'}`,
            `Patología: ${selectedForAssistant?.pathology || 'No registrada'}`,
            'Modo de respaldo local activo por indisponibilidad del servicio del asistente.',
          ],
        },
      });
      setAgentMessage(normalizeErrorMessage(error, 'Asistente externo no disponible. Se muestra orientación clínica local de respaldo.'));
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="app-shell login-shell">
        <div className="bg-ornament bg-left" />
        <div className="bg-ornament bg-right" />

        <header className="brand-header">
          <div className="brand-identity">
            <img src="/pechychon-logo.svg" alt="Logo Clinica Pechychon" className="brand-logo" />
          </div>
          <p className="eyebrow">CLINICA PECHYCHON</p>
          <h1>Centro Medico Pechychon</h1>
          <p className="lead">
            Atención clínica integral con historia digital segura, seguimiento de pacientes y apoyo inteligente para el cuerpo médico.
          </p>
          <p className="slogan">Cuidamos tu corazón, protegemos tu futuro.</p>
        </header>

        <main className="login-grid">
          <section className="card auth-card">
            <div className="auth-layout">
              <div>
                <h2>Ingreso del personal médico</h2>
                <p className="muted">Ingrese sus credenciales institucionales para acceder al portal clínico.</p>

                <form className="stack" onSubmit={login}>
                  <label>
                    Correo institucional
                    <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" />
                  </label>
                  <label>
                    Contraseña
                    <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" />
                  </label>
                  <label>
                    Licencia médica
                    <input value={licenseNumber} onChange={(event) => setLicenseNumber(event.target.value)} autoComplete="off" />
                  </label>
                  <button type="submit">Ingresar al portal</button>
                </form>
                <p className="status-text">{status}</p>
              </div>

              <aside className="auth-visual" aria-label="Ilustración clínica">
                <img src="/login-heart-pechy-animated.svg" alt="Corazón animado con marca Pechy" />
                <div className="floating-chip chip-one">Atención privada</div>
              </aside>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell clinic-shell">
      <div className="bg-ornament bg-left" />
      <div className="bg-ornament bg-right" />

      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <article key={toast.id} className={`toast toast-${toast.type}`}>
            <p>{toast.message}</p>
            <button type="button" className="toast-close" onClick={() => dismissToast(toast.id)}>Cerrar</button>
          </article>
        ))}
      </div>

      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <article key={toast.id} className={`toast toast-${toast.type}`}>
            <p>{toast.message}</p>
            <button type="button" className="toast-close" onClick={() => dismissToast(toast.id)}>Cerrar</button>
          </article>
        ))}
      </div>

      <header className="top-header card">
        <div className="header-copy">
          <div className="brand-identity compact">
            <img src="/pechychon-logo.svg" alt="Logo Clinica Pechychon" className="brand-logo" />
          </div>
          <p className="eyebrow">CLINICA PECHYCHON</p>
          <h1>Centro de Salud Pechychon</h1>
          <p className="muted">Sistema de gestión clínica para equipo médico y atención privada.</p>
          <p className="slogan">Cada latido importa: prevención, diagnóstico y cuidado continuo.</p>
          <div className="header-pills">
            <span>Urgencias</span>
            <span>Consulta externa</span>
            <span>Hospitalización</span>
          </div>
        </div>
        <div className="header-visual-wrap">
          <img src="/cardio-heart-hero.svg" alt="Corazón clínico" className="header-visual" />
          <div className="header-actions">
            <span className="badge">Sesión activa</span>
            <button className="ghost" type="button" onClick={clearSession}>Cerrar sesión</button>
          </div>
        </div>
      </header>

      <main className="main-layout">
        <aside className="card side-nav">
          <button className={activeTab === 'inicio' ? 'nav-btn active' : 'nav-btn'} type="button" onClick={() => setActiveTab('inicio')}>Inicio</button>
          <button className={activeTab === 'pacientes' ? 'nav-btn active' : 'nav-btn'} type="button" onClick={() => setActiveTab('pacientes')}>Pacientes</button>
          <button className={activeTab === 'observaciones' ? 'nav-btn active' : 'nav-btn'} type="button" onClick={() => setActiveTab('observaciones')}>Observaciones</button>
          <button className={activeTab === 'ia' ? 'nav-btn active' : 'nav-btn'} type="button" onClick={() => setActiveTab('ia')}>Apoyo diagnóstico</button>
          <button className={activeTab === 'agente' ? 'nav-btn active' : 'nav-btn'} type="button" onClick={() => setActiveTab('agente')}>Chamorro Bot</button>
        </aside>

        <section className="content-area">
          {activeTab === 'inicio' && (
            <section className="card section-card">
              <h2>Resumen de jornada</h2>
              <div className="live-strip" aria-hidden="true">
                <span>Admisiones</span>
                <span>Laboratorio</span>
                <span>Imagenología</span>
                <span>Triage</span>
                <span>Consulta especializada</span>
              </div>
              <div className="kpi-grid">
                <article>
                  <strong>{dashboard.totalPatients}</strong>
                  <span>Pacientes registrados</span>
                </article>
                <article>
                  <strong>{dashboard.activePatients}</strong>
                  <span>Pacientes activos</span>
                </article>
                <article>
                  <strong>{dashboard.observationCount}</strong>
                  <span>Observaciones recientes</span>
                </article>
                <article>
                  <strong>{dashboard.probability}</strong>
                  <span>Confianza última evaluación</span>
                </article>
              </div>
              <div className="highlight-box">
                <h3>Paciente en seguimiento</h3>
                <p>{dashboard.selectedPatient}</p>
                <h3>Resultado clínico reciente</h3>
                <p>{dashboard.prediction}</p>
              </div>
            </section>
          )}

          {activeTab === 'pacientes' && (
            <section className="card section-card">
              <h2>Gestión de pacientes</h2>

              <form className="compact-form" onSubmit={searchPatients}>
                <label>
                  Buscar por identificador (tipo|valor)
                  <input value={identifier} onChange={(event) => setIdentifier(event.target.value)} />
                </label>
                <button type="submit">Buscar</button>
              </form>

              <div className="inline-actions">
                <button type="button" onClick={importHeartDataset} disabled={importingDataset}>
                  {importingDataset ? 'Cargando lista del dataset...' : 'Usar lista de pacientes del dataset corazón'}
                </button>
                <button type="button" className="ghost" onClick={exportPatientsCsv}>Exportar CSV</button>
              </div>
              <p className="status-text">{importMessage}</p>

              <p className="status-text">{searchMessage}</p>

              <div className="filters-row">
                <label>
                  Buscar paciente
                  <input value={patientSearch} onChange={(event) => { setPatientSearch(event.target.value); setCurrentPage(1); }} placeholder="Nombre, ID o patología" />
                </label>
                <label>
                  Filtro por género
                  <select value={genderFilter} onChange={(event) => { setGenderFilter(event.target.value); setCurrentPage(1); }}>
                    <option value="all">Todos</option>
                    <option value="female">Femenino</option>
                    <option value="male">Masculino</option>
                    <option value="other">Otro</option>
                    <option value="unknown">No reportado</option>
                  </select>
                </label>
                <label>
                  Estado del paciente
                  <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setCurrentPage(1); }}>
                    <option value="all">Todos</option>
                    <option value="active">Activos</option>
                    <option value="inactive">Inactivos</option>
                  </select>
                </label>
                <label>
                  Filtro por patología
                  <select value={pathologyFilter} onChange={(event) => { setPathologyFilter(event.target.value); setCurrentPage(1); }}>
                    <option value="all">Todas</option>
                    {pathologyOptions.filter((item) => item !== 'all').map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Filas por página
                  <select value={String(pageSize)} onChange={(event) => { setPageSize(Number(event.target.value)); setCurrentPage(1); }}>
                    <option value="10">10</option>
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </select>
                </label>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Paciente</th>
                      <th>Identificación</th>
                      <th>Género</th>
                      <th>Nacimiento</th>
                      <th>Patología cardíaca</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPatients.length === 0 ? (
                      <tr>
                        <td colSpan="6" className="empty">No hay datos para mostrar.</td>
                      </tr>
                    ) : (
                      paginatedPatients.map((patient) => (
                        [
                          <tr
                            key={patient.key}
                            className={selectedPatient?.key === patient.key ? 'selected' : ''}
                            onClick={() => openPatientMenu(patient)}
                          >
                            <td>{patient.name}</td>
                            <td>{patient.identifier}</td>
                            <td>{formatGender(patient.gender)}</td>
                            <td>{patient.birthDate}</td>
                            <td>{patient.pathology || 'Sin patología registrada'}</td>
                            <td>{patient.active ? 'Activo' : 'Inactivo'}</td>
                          </tr>,
                          expandedPatientId === String(patient.id) && (
                            <tr className="action-row" key={`${patient.key}-actions`}>
                              <td colSpan="6">
                                <div className="row-action-menu">
                                  <label>
                                    Comentario del procedimiento (obligatorio)
                                    <textarea value={procedureComment} onChange={(event) => setProcedureComment(event.target.value)} rows={2} placeholder="Explique por qué realizará la acción" />
                                  </label>
                                  <div className="inline-actions">
                                    <button type="button" onClick={() => {
                                      setActiveTab('observaciones');
                                      setObservationPatientId(String(patient.id));
                                      setExpandedPatientId('');
                                      setEditingPatientId('');
                                    }}>
                                      Hacer observación
                                    </button>
                                    <button type="button" onClick={() => {
                                      setActiveTab('agente');
                                      setAgentPatientId(String(patient.id));
                                      setExpandedPatientId('');
                                      setEditingPatientId('');
                                    }}>
                                      Chamorro Bot
                                    </button>
                                    <button type="button" className="ghost" onClick={() => setEditingPatientId(String(patient.id))}>Editar paciente</button>
                                  </div>
                                  {editingPatientId === String(patient.id) && (
                                    <div className="inline-actions edit-actions">
                                      {patient.active ? (
                                        <button type="button" className="ghost" onClick={() => askConfirmAction('deactivate', patient)}>Desactivar paciente</button>
                                      ) : (
                                        <button type="button" className="ghost" onClick={() => askConfirmAction('activate', patient)}>Activar paciente</button>
                                      )}
                                      <button type="button" className="ghost danger" onClick={() => askConfirmAction('remove', patient)}>Eliminar de la tabla</button>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ),
                        ]
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="table-footer">
                <p className="muted">
                  Mostrando {filteredPatients.length === 0 ? 0 : (currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, filteredPatients.length)} de {filteredPatients.length} paciente(s).
                </p>
                <div className="pager">
                  <button type="button" className="ghost" disabled={currentPage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>Anterior</button>
                  <span>Página {currentPage} / {totalPages}</span>
                  <button type="button" className="ghost" disabled={currentPage >= totalPages} onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}>Siguiente</button>
                </div>
              </div>

              <div className="patient-summary">
                <h3>Ficha rápida</h3>
                <p><strong>Nombre:</strong> {selectedPatient?.name || 'Sin selección'}</p>
                <p><strong>Identificación:</strong> {selectedPatient?.identifier || 'Sin selección'}</p>
                <p><strong>Nacimiento:</strong> {selectedPatient?.birthDate || 'Sin selección'}</p>
                <p><strong>Patología:</strong> {selectedPatient?.pathology || 'Sin selección'}</p>
                {deleteMessage && <p className="status-text">{deleteMessage}</p>}
              </div>

              <div className="action-log-box">
                <h3>Registro de procedimientos</h3>
                {actionLogs.length === 0 ? (
                  <p className="muted">No hay procedimientos registrados en esta sesión.</p>
                ) : (
                  <ul>
                    {actionLogs.map((log) => (
                      <li key={log.id}>
                        <strong>{log.action}</strong> - {log.patientName} ({log.patientIdentifier})
                        <br />
                        <span>{log.timestamp} | Motivo: {log.comment}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <h3>Registrar paciente</h3>
              <form className="grid-form" onSubmit={createPatient}>
                <label>
                  Tipo ID
                  <select
                    value={newPatient.identifierType}
                    onChange={(event) => setNewPatient((current) => ({ ...current, identifierType: event.target.value }))}
                  >
                    <option value="CC">CC</option>
                    <option value="TI">TI</option>
                    <option value="CE">CE</option>
                    <option value="PS">PS</option>
                  </select>
                </label>
                <label>
                  Número ID
                  <input
                    value={newPatient.identifierValue}
                    onChange={(event) => setNewPatient((current) => ({ ...current, identifierValue: event.target.value }))}
                  />
                </label>
                <label>
                  Género
                  <select
                    value={newPatient.gender}
                    onChange={(event) => setNewPatient((current) => ({ ...current, gender: event.target.value }))}
                  >
                    <option value="female">Femenino</option>
                    <option value="male">Masculino</option>
                    <option value="other">Otro</option>
                    <option value="unknown">No reportado</option>
                  </select>
                </label>
                <label>
                  Apellidos
                  <input
                    value={newPatient.family}
                    onChange={(event) => setNewPatient((current) => ({ ...current, family: event.target.value }))}
                  />
                </label>
                <label>
                  Nombres
                  <input
                    value={newPatient.given}
                    onChange={(event) => setNewPatient((current) => ({ ...current, given: event.target.value }))}
                  />
                </label>
                <label>
                  Fecha de nacimiento
                  <input
                    type="date"
                    value={newPatient.birthDate}
                    onChange={(event) => setNewPatient((current) => ({ ...current, birthDate: event.target.value }))}
                  />
                </label>
                <button type="submit">Registrar paciente</button>
              </form>

              <p className="status-text">{createMessage}</p>
            </section>
          )}

          {activeTab === 'observaciones' && (
            <section className="card section-card">
              <h2>Observaciones clínicas</h2>
              <form className="grid-form" onSubmit={fetchObservations}>
                <label>
                  Paciente
                  <select value={observationPatientId} onChange={(event) => setObservationPatientId(event.target.value)}>
                    {patientOptions.length === 0 ? (
                      <option value="">Sin pacientes</option>
                    ) : (
                      patientOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))
                    )}
                  </select>
                </label>
                <label>
                  Código LOINC (opcional)
                  <input value={loincCode} onChange={(event) => setLoincCode(event.target.value)} />
                </label>
                <label>
                  Cantidad máxima
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={observationCount}
                    onChange={(event) => setObservationCount(event.target.value)}
                  />
                </label>
                <button type="submit">Consultar</button>
              </form>

              <h3>Registrar observación</h3>
              <form className="grid-form" onSubmit={createObservation}>
                <label>
                  Código LOINC
                  <input value={newObservationCode} onChange={(event) => setNewObservationCode(event.target.value)} />
                </label>
                <label>
                  Valor
                  <input value={newObservationValue} onChange={(event) => setNewObservationValue(event.target.value)} />
                </label>
                <label>
                  Unidad
                  <input value={newObservationUnit} onChange={(event) => setNewObservationUnit(event.target.value)} />
                </label>
                <label className="full-width">
                  Comentario del procedimiento (obligatorio)
                  <textarea value={observationComment} onChange={(event) => setObservationComment(event.target.value)} rows={3} placeholder="Explique por qué se registra la observación" />
                </label>
                <button type="submit">Guardar observación</button>
              </form>

              <p className="status-text">{observationMessage}</p>

              <div className="observation-list">
                {summarizeObservation(observationData).length === 0 ? (
                  <p className="empty">No hay observaciones para mostrar.</p>
                ) : (
                  summarizeObservation(observationData).map((item) => (
                    <article key={item.id} className="observation-item">
                      <strong>{item.label}</strong>
                      <span>{item.value}</span>
                      <small>{item.date}</small>
                    </article>
                  ))
                )}
              </div>
            </section>
          )}

          {activeTab === 'ia' && (
            <section className="card section-card">
              <h2>Apoyo diagnóstico</h2>
              <div className="alejo-assistant card">
                <img src="/alejo-bot.svg" alt="Alejo asistente IA" className="alejo-avatar" />
                <div>
                  <h3>Alejo, asistente de análisis</h3>
                  <p className="muted">{alejoMessage}</p>
                </div>
                <button type="button" className="ghost" onClick={configureWithAlejo}>Configurar con Alejo</button>
              </div>
              <form className="grid-form" onSubmit={runInference}>
                <label>
                  Paciente
                  <select value={inferencePatientId} onChange={(event) => setInferencePatientId(event.target.value)}>
                    {patientOptions.length === 0 ? (
                      <option value="">Sin pacientes</option>
                    ) : (
                      patientOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))
                    )}
                  </select>
                </label>
                <label>
                  Tipo de modelo
                  <select value={modelType} onChange={(event) => setModelType(event.target.value)}>
                    <option value="tabular">Tabular</option>
                    <option value="image">Imagen</option>
                  </select>
                </label>
                <label>
                  Modelo
                  <input value={modelName} onChange={(event) => setModelName(event.target.value)} />
                </label>
                <button type="submit">Evaluar paciente</button>
              </form>

              <p className="status-text">{inferenceMessage}</p>

              <div className="kpi-grid single-row">
                <article>
                  <strong>{inferenceData?.prediction || 'Sin resultado'}</strong>
                  <span>Predicción</span>
                </article>
                <article>
                  <strong>{typeof inferenceData?.probability === 'number' ? `${Math.round(inferenceData.probability * 100)}%` : 'No disponible'}</strong>
                  <span>Probabilidad</span>
                </article>
                <article>
                  <strong>{inferenceData?.calibrated === false ? 'No' : 'Sí'}</strong>
                  <span>Calibrado</span>
                </article>
              </div>
            </section>
          )}

          {activeTab === 'agente' && (
            <section className="card section-card">
              <h2>Chamorro Bot</h2>
              <p className="muted">Realice preguntas de riesgo cardíaco y apoyo a la decisión clínica por paciente.</p>

              <form className="grid-form" onSubmit={queryAgent}>
                <label>
                  Paciente
                  <select value={agentPatientId} onChange={(event) => setAgentPatientId(event.target.value)}>
                    {patientOptions.length === 0 ? (
                      <option value="">Sin pacientes</option>
                    ) : (
                      patientOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))
                    )}
                  </select>
                </label>
                <label>
                  Estrategia de consulta
                  <select value={agentStrategy} onChange={(event) => setAgentStrategy(event.target.value)}>
                    <option value="hybrid">Híbrida</option>
                    <option value="bm25">BM25</option>
                    <option value="dense">Vectorial</option>
                    <option value="multi_query">Multi-consulta</option>
                  </select>
                </label>
                <label>
                  Modelo de apoyo
                  <select value={agentModelType} onChange={(event) => setAgentModelType(event.target.value)}>
                    <option value="tabular">Tabular</option>
                    <option value="image">Imagen</option>
                  </select>
                </label>
                <label>
                  Sesión (opcional)
                  <input value={agentSessionId} onChange={(event) => setAgentSessionId(event.target.value)} placeholder="Se completa automáticamente" />
                </label>
                <label className="full-width">
                  Pregunta clínica
                  <textarea value={agentQuestion} onChange={(event) => setAgentQuestion(event.target.value)} rows={5} />
                </label>
                <button type="submit">Consultar Chamorro Bot</button>
              </form>

              <p className="status-text">{agentMessage}</p>

              {agentData && (
                <div className="agent-response">
                  <h3>Respuesta del asistente</h3>
                  <p>
                    {typeof agentData?.answer?.prediction?.prediction === 'string'
                      ? agentData.answer.prediction.prediction
                      : typeof agentData?.answer?.prediction === 'string'
                        ? agentData.answer.prediction
                        : 'Se generó una respuesta clínica para este caso.'}
                  </p>

                  <h4>Contextos utilizados</h4>
                  <ul>
                    {(agentData?.answer?.retrieved_contexts || []).slice(0, 4).map((context, index) => (
                      <li key={`ctx-${index}`}>{context}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}
        </section>
      </main>

      {pendingConfirm && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-label="Confirmación de acción">
          <div className="confirm-card">
            <h3>Confirmación requerida</h3>
            <p>{pendingConfirm.message}</p>
            <p className="muted">Comentario: {pendingConfirm.comment}</p>
            <div className="inline-actions">
              <button type="button" className="ghost" onClick={() => setPendingConfirm(null)}>Cancelar</button>
              <button type="button" onClick={executeConfirmedAction}>Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
