# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
UID_ROOT = 1
import netsvc
from osv import osv, fields
from tools.translate import _

class mrp_production(osv.osv):
    
    _inherit = 'mrp.production'

    def _progress_rate(self, cr, uid, ids, names, arg, context=None):
        production_status_obj =  self.pool.get('mrp.production.status')
        res = dict([(id, {'progress_rate':0.0}) for id in ids])
        stages = ['s1','s2','s3','s4','s5'] 
        
        # compute progress rates    
        for id in ids:
            line_ids = production_status_obj.search(cr, uid, [('production_id','=',id)])
            results = production_status_obj.read(cr, uid, line_ids, ['product_qty'] + stages + ['num_stations'])
            num_products = len(results) # I.e., 5 product lines
            actual_total = 0.0
            for result in results:
                actual_line_total = 0.0
                planned_line = result['product_qty'] * result['num_stations']
                if planned_line:
                    for stage in stages:
                        actual_line = result[stage]
                        actual_line_total += actual_line
                    
                    ratio_completion = (actual_line_total/planned_line)
                    actual_total += ratio_completion > 1 and 1 or ratio_completion
                    res[id]['progress_rate'] = 100 * (actual_total/num_products)
                else:
                    res[id]['progress_rate'] = 0.0
        return res
    
    def _get_mrp_proudction(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('mrp.production.status').browse(cr, uid, ids, context=context):
            result[line.production_id.id] = True
        return result.keys()
    
    _columns = {
        'status_lines': fields.one2many('mrp.production.status', 'production_id', 'Status Tracking',
            readonly=False, states={'done':[('readonly',True)]}),
        'progress_rate': fields.function(_progress_rate, multi="progress", string='Progress', type='float', group_operator="avg", help="Percent of tasks closed according to the total of tasks todo.",
            store = {
                'mrp.production': (lambda self, cr, uid, ids, c={}: ids, ['status_lines','num_stations'], 10),
                'mrp.production.status': (_get_mrp_proudction, ['s1', 's2', 's3', 's4', 's5', 'num_stations'], 10),
            }),      
        'num_stations': fields.selection([(1,'1'), (2,'2'), (3,'3'), (4,'4'), (5,'5')], '# Stations', required=True, readonly=False, states={'done':[('readonly',True)]}),
    }
    _defaults = {
        'num_stations': 5
    }    
    
    # When create stock.move, also create for status tracking tab
    def _make_production_consume_line(self, cr, uid, production_line, parent_move_id, source_location_id=False, context=None):
        move_id = super(mrp_production, self)._make_production_consume_line(cr, uid, production_line, parent_move_id, source_location_id=source_location_id, context=context)
        move = self.pool.get('stock.move').browse(cr, uid, move_id)
        self.pool.get('mrp.production.status').create(cr, uid, {
            'production_id': production_line.production_id.id,
            'product_id': move.product_id.id,
            'product_qty': production_line.product_qty,
            'product_uom': production_line.product_uom.id,
        })
        return move_id
    
    def reset_stations(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
            
        status_line_obj = self.pool.get('mrp.production.status')
        num_stations = context.get('num_stations', False)
        
        if not num_stations:
            return False
        
        line_ids = status_line_obj.search(cr, uid, [('production_id', 'in', ids)], context=context)
        status_line_obj.write(cr, uid, line_ids, {'num_stations': num_stations}, context=context)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload'
                }           
    
mrp_production()

class mrp_production_status(osv.osv):
    
    _name = 'mrp.production.status'
    _description = 'Production Status Tracking'
    _order = 'sequence, id'
    
    def _get_product_sequence(self, cr, uid, ids, name, arg, context=None):
        res = {}
        product_obj = self.pool.get('product.product')
        for product_line in self.browse(cr, uid, ids, context=context):
            result = product_obj.read(cr, uid, [product_line.product_id.id], ['sequence'])
            if result[0]['sequence']:
                res[product_line.id] = result[0]['sequence'] or 10000
        return res

    _columns = {
        'sequence': fields.function(_get_product_sequence, string='Sequence', type='integer', store=True),
        'production_id': fields.many2one('mrp.production', 'Manufacturing Order', required=True, ondelete='cascade', select=True),
        'product_id': fields.many2one('product.product', 'Product', readonly=True),
        'product_qty': fields.float('Quantity', readonly=True),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', readonly=True),
        's1': fields.float('S1'),
        's2': fields.float('S2'),
        's3': fields.float('S3'),
        's4': fields.float('S4'),
        's5': fields.float('S5'),
        'num_stations': fields.selection([(1,'1'), (2,'2'), (3,'3'), (4,'4'), (5,'5')], '# Stations', required=True),
    }
    _defaults = {
        'num_stations': 5
    }
    
    def fields_get(self, cr, uid, fields=None, context=None):
        res = super(mrp_production_status, self).fields_get(cr, uid, fields, context)
        user_groups = set(self.pool.get('res.users').read(cr, UID_ROOT, uid, ['groups_id'])['groups_id'])
        mod_obj = self.pool.get('ir.model.data')
        chk_groups = ['s1', 's2', 's3', 's4', 's5']
        for chk_group in chk_groups:
            gid = mod_obj.get_object_reference(cr, uid, 'mrp_production_status', 'group_%s' % (chk_group,))
            if user_groups.issuperset(set([gid[1]])):
                res[chk_group].update({'readonly': False})
            else:
                res[chk_group].update({'readonly': True})
        return res
    
    def onchange_ss(self, cr, uid, ids, product_qty, prev, this, context=None):
        if context is None:
            context = {}
        if prev != 0 and this > prev:
            raise osv.except_osv(_('Warning!'),
                                 _('Value entered (%s) must be less or equal to previous stage (%s)') % (this, prev))
        if this > product_qty:
            raise osv.except_osv(_('Warning!'),
                                 _('Value entered (%s) must be less or equal product quantity (%s)') % (this, product_qty))
        return True
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(mrp_production_status, self).write(cr, uid, ids, vals, context=context)
        if not isinstance(ids, list):
            ids = [ids]        
        for mp_status in self.pool.get('mrp.production.status').browse(cr, uid, ids):
            if mp_status.s1 > mp_status.product_qty or \
                mp_status.s2 > mp_status.product_qty or \
                mp_status.s3 > mp_status.product_qty or \
                mp_status.s4 > mp_status.product_qty or \
                mp_status.s5 > mp_status.product_qty:
                raise osv.except_osv(_('Can not save change!'),
                                 _('Some subsequence value in Status Tracking still greater than product quantity'))
        return res
        
mrp_production_status()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
