select *, quantity - delivered_qty balance
from (select *,
	(quantity - inject) inject_bal,
	inject / quantity * 100 inject_percent,
	(quantity - door) door_bal,
	(quantity - steel) steel_bal,
	(select sum(product_qty) from stock_picking p
	join stock_move m on m.picking_id = p.id 
	where m.state = 'done' and p.ref_order_id = b.order_id and position(b.mo in p.origin) > 0) delivered_qty
	from (
		select mo_id, order_id, picking_id, order_type, mo_date, do_date, mo, cust, project, thick,
		sum(quantity) quantity,
		sum(inject) inject,
		sum(door) door,
		sum(steel) steel
		from (
			select prd.id mo_id, prd.order_id, prd.target_picking_id picking_id, 
			tag.name order_type, prd.date_planned mo_date, pick.min_date do_date, prd.name mo, cust.name cust, 
			so.ref_project_name project, 
			so.name so, (select t.name from mrp_production prd2
					join product_product pp on pp.id = prd2.product_id
					join bom_choice_thick t on t.id = pp."T"
					where prd2.parent_id = prd.id
					and pp."T" is not null limit 1) as thick,
			coalesce(status.product_qty, 0.0) quantity,
			coalesce(status.s3, 0.0) inject,
			coalesce(status.s4, 0.0) door,
			coalesce(status.s1, 0.0) steel
			from mrp_production prd
			join mrp_production_status status on status.production_id = prd.id
			left outer join sale_order so on so.id = prd.order_id
			left outer join res_partner cust on cust.id = prd.partner_id
			left outer join product_tag tag on tag.id = so.product_tag_id
			left outer join stock_picking pick on pick.id = prd.target_picking_id
			where prd.parent_id is null
			and prd.state in ('confirmed', 'ready', 'in_production', 'done')
			-- For performance, just make sure that we screen out all delivered MO
			and prd.id in (select mo_id from
					(select order_id, prd.id mo_id, prd.name mo_name, sum(status.product_qty) qty
					from mrp_production prd
					join mrp_production_status status on status.production_id = prd.id
					where prd.parent_id is null
					and prd.order_id is not null
					group by prd.order_id, prd.id, prd.name) a
					where a.qty >  (select sum(product_qty) from stock_picking p
							join stock_move m on m.picking_id = p.id
							where p.ref_order_id = a.order_id and position(a.mo_name in p.origin) > 0))
		) a
	group by mo_id, order_id, picking_id, order_type, mo_date, do_date, mo, cust, project, thick
	) b
) c