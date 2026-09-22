-- La API que ve el navegador. Aplicado en Supabase con apply_migration como
-- "funciones_de_acceso_del_formulario", justo despues de 01_tablas.sql.
--
-- Son cuatro funciones y nada mas: las tablas quedan cerradas (01_tablas.sql),
-- asi que con la clave publica no se puede listar nada, solo llamar a esto.
-- Las llama Demo/frontend/public/experiencia/js/datos.js.

-- Cedulas y telefonos llegan escritos de mil formas ("1.020.304.050",
-- "+57 315 849 0324"). Se comparan siempre por sus digitos.
create or replace function public.solo_digitos(txt text)
returns text
language sql
immutable
set search_path = ''
as $$
  select regexp_replace(coalesce(txt, ''), '[^0-9]', '', 'g')
$$;


-- 1. Guardar lo que la persona respondio y lo que se le recomendo.
create or replace function public.guardar_consulta(
  p_cedula     text,
  p_nombre     text,
  p_apellido   text,
  p_correo     text,
  p_telefono   text,
  p_respuestas jsonb,
  p_resultados jsonb
)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_cedula text := public.solo_digitos(p_cedula);
  v_tel    text := public.solo_digitos(p_telefono);
  v_id     bigint;
begin
  if length(v_cedula) < 5 then
    raise exception 'La cedula no parece valida.';
  end if;
  if length(v_tel) < 10 then
    raise exception 'El telefono no parece valido.';
  end if;

  -- EL TELEFONO NO SE PISA A PROPOSITO. Si se actualizara, cualquiera podria
  -- reclamar una cedula ajena mandandola con su propio numero y, al quedar los
  -- dos datos bajo su control, leer las consultas de esa persona.
  insert into public.leads (cedula, nombre, apellido, correo, telefono)
  values (v_cedula, p_nombre, p_apellido, p_correo, v_tel)
  on conflict (cedula) do update
    set nombre         = excluded.nombre,
        apellido       = excluded.apellido,
        correo         = excluded.correo,
        actualizado_en = now();

  insert into public.consultas (cedula, respuestas, resultados)
  values (v_cedula, p_respuestas, p_resultados)
  returning id into v_id;

  return v_id;
end
$$;


-- 2. Recuperar la ultima consulta. Exige los DOS datos: sin el telefono
--    correcto no devuelve nada, ni siquiera dice si la cedula existe.
create or replace function public.buscar_resultados(
  p_cedula   text,
  p_telefono text
)
returns table (
  consulta_id bigint,
  nombre      text,
  apellido    text,
  correo      text,
  telefono    text,
  respuestas  jsonb,
  resultados  jsonb,
  creado_en   timestamptz
)
language sql
security definer
stable
set search_path = ''
as $$
  select c.id, l.nombre, l.apellido, l.correo, l.telefono,
         c.respuestas, c.resultados, c.creado_en
  from public.leads l
  join public.consultas c on c.cedula = l.cedula
  where l.cedula = public.solo_digitos(p_cedula)
    and right(public.solo_digitos(l.telefono), 10)
        = right(public.solo_digitos(p_telefono), 10)
  order by c.creado_en desc
  limit 1
$$;


-- 3. Anotar que proyecto le intereso.
create or replace function public.marcar_interes(
  p_cedula      text,
  p_telefono    text,
  p_proyecto    text,
  p_consulta_id bigint default null
)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_cedula text := public.solo_digitos(p_cedula);
  v_id     bigint;
begin
  if not exists (
    select 1 from public.leads l
    where l.cedula = v_cedula
      and right(public.solo_digitos(l.telefono), 10)
          = right(public.solo_digitos(p_telefono), 10)
  ) then
    raise exception 'No encontramos esa combinacion de cedula y telefono.';
  end if;

  insert into public.intereses (cedula, consulta_id, proyecto)
  values (v_cedula, p_consulta_id, p_proyecto)
  returning id into v_id;

  return v_id;
end
$$;


-- 4. Marcar que SI hubo intencion de compra: en la llamada se agendo cita.
--    La senal es `fecha_de_seguimiento`, que Dapta devuelve en el analisis
--    post-llamada. Si viene con fecha, quedo una cita puesta.
create or replace function public.marcar_intencion(
  p_cedula            text,
  p_telefono          text,
  p_proyecto          text,
  p_fecha_seguimiento text default null,
  p_temperatura       text default null
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_cedula text := public.solo_digitos(p_cedula);
  v_hubo   boolean := coalesce(nullif(trim(p_fecha_seguimiento), ''), '') <> '';
begin
  if not exists (
    select 1 from public.leads l
    where l.cedula = v_cedula
      and right(public.solo_digitos(l.telefono), 10)
          = right(public.solo_digitos(p_telefono), 10)
  ) then
    raise exception 'No encontramos esa combinacion de cedula y telefono.';
  end if;

  update public.intereses
     set intencion_compra  = v_hubo,
         fecha_seguimiento = p_fecha_seguimiento,
         temperatura_lead  = p_temperatura,
         actualizado_en    = now()
   where cedula = v_cedula
     and proyecto = p_proyecto;

  if not found then
    insert into public.intereses
      (cedula, proyecto, intencion_compra, fecha_seguimiento, temperatura_lead)
    values (v_cedula, p_proyecto, v_hubo, p_fecha_seguimiento, p_temperatura);
  end if;

  return v_hubo;
end
$$;


-- Solo estas cuatro, y solo para el rol anonimo del navegador.
revoke all on function public.guardar_consulta(text, text, text, text, text, jsonb, jsonb) from public;
revoke all on function public.buscar_resultados(text, text) from public;
revoke all on function public.marcar_interes(text, text, text, bigint) from public;
revoke all on function public.marcar_intencion(text, text, text, text, text) from public;

grant execute on function public.guardar_consulta(text, text, text, text, text, jsonb, jsonb) to anon;
grant execute on function public.buscar_resultados(text, text) to anon;
grant execute on function public.marcar_interes(text, text, text, bigint) to anon;
grant execute on function public.marcar_intencion(text, text, text, text, text) to anon;
