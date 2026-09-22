-- Leadify — esquema del formulario. Aplicado en Supabase (Postgres) con
-- apply_migration como "esquema_inicial_leads_consultas_intereses".
--
-- Tres tablas: quien es la persona, que respondio cada vez, y que proyecto le
-- intereso. Se separan porque una misma persona puede volver y llenar el
-- formulario otra vez, y puede interesarse en mas de un proyecto.

-- La persona. La cedula es la llave: es lo que la identifica al volver.
create table public.leads (
  cedula          text primary key,
  nombre          text not null,
  apellido        text,
  correo          text,
  telefono        text not null,
  creado_en       timestamptz not null default now(),
  actualizado_en  timestamptz not null default now()
);

comment on table public.leads is
  'Datos de contacto que deja la persona en el carne del formulario.';

-- Una fila por vez que alguien completa el cuestionario. Guarda las respuestas
-- y los proyectos recomendados, que es lo que se le devuelve si vuelve.
create table public.consultas (
  id          bigint generated always as identity primary key,
  cedula      text not null references public.leads(cedula) on delete cascade,
  respuestas  jsonb not null,
  resultados  jsonb not null,
  creado_en   timestamptz not null default now()
);

create index consultas_cedula_fecha on public.consultas (cedula, creado_en desc);

comment on table public.consultas is
  'Cada envio del cuestionario: las 7 respuestas y los proyectos recomendados.';

-- El proyecto que le intereso y si acabo agendando cita con un asesor.
-- `intencion_compra` se pone en true cuando Dapta devuelve una fecha de
-- seguimiento tras la llamada, que es la senal de que se agendo (ver
-- `fecha_de_seguimiento` en el webhook post-call de Demo/backend/api/app.py).
create table public.intereses (
  id                 bigint generated always as identity primary key,
  cedula             text not null references public.leads(cedula) on delete cascade,
  consulta_id        bigint references public.consultas(id) on delete set null,
  proyecto           text not null,
  intencion_compra   boolean not null default false,
  fecha_seguimiento  text,
  temperatura_lead   text,
  creado_en          timestamptz not null default now(),
  actualizado_en     timestamptz not null default now()
);

create index intereses_cedula on public.intereses (cedula);

comment on table public.intereses is
  'Proyecto de interes por persona, y si agendo cita con un asesor.';

comment on column public.intereses.intencion_compra is
  'true cuando en la llamada se agendo una cita con un asesor.';

-- NADIE lee estas tablas directo. El navegador lleva una clave publica, asi
-- que dejarlas abiertas significaria que cualquiera pueda listar las cedulas y
-- telefonos de todo el mundo. El acceso va por las funciones de
-- 02_funciones.sql, que exigen cedula Y telefono para devolver algo.
alter table public.leads      enable row level security;
alter table public.consultas  enable row level security;
alter table public.intereses  enable row level security;

revoke all on public.leads      from anon, authenticated;
revoke all on public.consultas  from anon, authenticated;
revoke all on public.intereses  from anon, authenticated;
