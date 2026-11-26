-- CI-only fixture: a tiny pilot rubric so the rolled-back tests have a rubric to use.
-- Never applied to the live database (which already holds the real rubric).
do $$
declare v_rv uuid; v_cat uuid; i int;
begin
  insert into public.rubric_versions(version_code, position_group, methodology_version, scoring_anchors_version, status, source_document)
    values ('CI-FIXTURE-1', 'ci', 'ci', 'ci', 'pilot', 'ci fixture') returning id into v_rv;
  insert into public.rubric_categories(rubric_version_id, category_code, category_name, category_weight_percent, sort_order)
    values (v_rv, 'CAT1', 'Category 1', 100, 1) returning id into v_cat;
  for i in 1..3 loop
    insert into public.rubric_criteria(rubric_version_id, rubric_category_id, criterion_code, criterion_name, weight_percent, score_anchors, sort_order)
      values (v_rv, v_cat, 'C'||i, 'Criterion '||i, 33,
        jsonb_build_object('1–2','a','3–4','b','5–6','c','7–8','d','9','e','10','f'), i);
  end loop;
end $$;

-- CI-only staff account (tests that look up an existing admin/editor use this one).
do $$
declare v_u uuid := gen_random_uuid();
begin
  insert into auth.users(id, email) values (v_u, 'ci-admin@example.invalid');
  insert into public.user_roles(user_id, role) values (v_u, 'admin');
end $$;
